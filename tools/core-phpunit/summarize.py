#!/usr/bin/env python3
"""Summarize a PHPUnit JUnit XML log from the R-009 harness.

Outputs (stdout): overall counts line, then CSV of per-directory and per-group
counts. Optional files:
  --dir-csv PATH     per test directory (tests/phpunit/tests/<dir>) counts
  --group-csv PATH   per @group counts (groups read from test source docblocks)
  --fail-csv PATH    one row per failing/erroring test with normalized signature
  --sig-csv PATH     failure signatures with counts and example tests
  --src ROOT         wordpress-develop root to read @group annotations (optional)
  --baseline PATH    fail-csv of a control run; tests failing there are tagged
                     'control-fail' in the triage (environmental)

Statuses: pass, failure, error, skipped (skipped includes incomplete/risky
reported as <skipped/>).
"""
import argparse
import html
import collections
import csv
import os
import re
import sys
import xml.etree.ElementTree as ET

TESTS_ROOT = "tests/phpunit/tests/"


_XML_INVALID = re.compile("[^\u0009\u000a\u000d\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def load_tree(path):
    """Parse JUnit XML; PHPUnit 9 can emit characters XML 1.0 forbids (e.g.
    U+FFFE from data-set names or captured output), so strip those first."""
    try:
        return ET.parse(path)
    except ET.ParseError:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8", errors="replace")
        return ET.ElementTree(ET.fromstring(_XML_INVALID.sub("\ufffd", text)))


def iter_cases(path):
    tree = load_tree(path)
    for tc in tree.iter("testcase"):
        status = "pass"
        msg = ""
        warn = False
        for child in tc:
            if child.tag in ("failure", "error"):
                status = child.tag
                msg = (child.text or "") or child.get("message", "")
                break
            if child.tag == "warning":
                warn = True
            if child.tag == "skipped":
                status = "skipped"
                msg = child.text or child.get("message", "") or ""
        # Captured output can be megabytes; the first 20k chars carry the
        # first error, which is what signatures and triage use.
        msg = msg[:20000]
        yield {
            "class": tc.get("class") or tc.get("classname") or "",
            "name": tc.get("name") or "",
            "file": tc.get("file") or "",
            "time": float(tc.get("time") or 0.0),
            "status": status,
            "message": msg,
            "warning": warn,
        }


def test_dir(file_path):
    i = file_path.find(TESTS_ROOT)
    if i < 0:
        return "(unknown)"
    rel = file_path[i + len(TESTS_ROOT):]
    parts = rel.split("/")
    return parts[0] if len(parts) > 1 else "(root)"


_group_cache = {}


def groups_for(file_path, src_root, klass):
    if not src_root or not file_path:
        return []
    i = file_path.find(TESTS_ROOT)
    if i < 0:
        return []
    local = os.path.join(src_root, file_path[i:])
    if local not in _group_cache:
        try:
            text = open(local, encoding="utf-8", errors="replace").read()
        except OSError:
            text = ""
        # Class-level groups: docblock immediately before "class X".
        m = re.search(r"/\*\*((?:(?!\*/).)*)\*/\s*(?:abstract\s+|final\s+)?class\s", text, re.S)
        cls_groups = re.findall(r"@group\s+([\w\-]+)", m.group(1)) if m else []
        _group_cache[local] = sorted(set(cls_groups))
    return _group_cache[local]


NORMALIZERS = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), "<uuid>"),
    (re.compile(r"/srv/wordpress-develop/[^\s:'\"]+"), "<path>"),
    (re.compile(r"'[^']{0,200}'"), "'<s>'"),
    (re.compile(r"\"(?![A-Za-z_][\w.]*\")[^\"]{0,200}\""), '"<s>"'),
    (re.compile(r"\b\d+(\.\d+)?\b"), "<n>"),
    (re.compile(r"\s+"), " "),
]


def first_line(msg):
    for line in msg.strip().splitlines():
        line = line.strip()
        if line and not line.startswith("Tests_") and "::" not in line[:80]:
            return line
    return msg.strip().splitlines()[0] if msg.strip() else ""


def signature(msg):
    """Normalize the most informative line of a failure message."""
    text = msg.strip()
    # Prefer an embedded database error if present.
    m = re.search(r"(WordPress database error[^\n]*|SQLSTATE\[[^\n]*|ERROR: [^\n]*)", text)
    line = m.group(1) if m else first_line(text)
    line = line.split(" for query ", 1)[0]
    line = re.split(r"<br\s*/?>|<code>", line)[0]
    line = html.unescape(re.sub(r"<[^>]+>", "", line))
    line = re.sub(r"^WordPress database error:?\s*\[?", "DB error: ", line).rstrip("]")
    line = re.sub(r"^This test printed output: ", "", line)
    for rx, rep in NORMALIZERS:
        line = rx.sub(rep, line)
    return line.strip()[:240]


UUID_LITERAL = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

BUCKET_RULES = [
    ("uuid-identity", re.compile(
        r"uuid|could not be converted to int|must be of type int|invalid input syntax for type (bigint|integer)"
        r"|trailing junk after numeric literal", re.I)),
    ("schema/ddl", re.compile(
        r"relation \S+ does not exist|unknown column|column \S+ does not exist|undefined (table|column)"
        r"|statement type '(create|alter|drop|show|describe|truncate|optimize|rename)'|temporary table", re.I)),
    ("harness/environment", re.compile(
        r"current transaction is aborted|wp-includes/js|script module file|\.min\.js|ghostscript|timed out", re.I)),
    ("sql-dialect", re.compile(
        r"syntax error|mysql-only keyword|statement type '|double-quoted|sql comments|unterminated quoted"
        r"|function \S+ does not exist|operator does not exist|duplicate key|group by|found_rows|sqlstate", re.I)),
]


def classify(text):
    for bucket, rx in BUCKET_RULES:
        if rx.search(text):
            return bucket
    return None


def triage(msg):
    """Heuristic bucket for PostgreSQL failures (see R-009 report).

    The first database error in the failure text decides the bucket; if there
    is none, the whole text is scanned, and a UUIDv7 literal in an assertion
    message (e.g. "'0193...' is identical to 1") counts as uuid-identity.
    """
    m = re.search(r"(WordPress database error[^\n]*|SQLSTATE\[[^\n]*)", msg)
    if m:
        b = classify(m.group(1))
        if b:
            return b
    b = classify(msg)
    if b:
        return b
    if UUID_LITERAL.search(msg):
        return "uuid-identity"
    return "unknown"


def counts_table(cases, keyfn):
    table = collections.defaultdict(collections.Counter)
    for c in cases:
        for k in keyfn(c):
            table[k][c["status"]] += 1
            table[k]["total"] += 1
            table[k]["time"] += c["time"]
    return table


def write_counts(path, header, table):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([header, "total", "pass", "failure", "error", "skipped", "pass_rate_pct", "pass_rate_excl_skipped_pct", "seconds"])
        for k in sorted(table, key=lambda x: (-table[x]["total"], x)):
            r = table[k]
            ran = r["total"] - r["skipped"]
            w.writerow([
                k, r["total"], r["pass"], r["failure"], r["error"], r["skipped"],
                f"{100.0 * r['pass'] / r['total']:.2f}" if r["total"] else "",
                f"{100.0 * r['pass'] / ran:.2f}" if ran else "",
                f"{r['time']:.1f}",
            ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("junit")
    ap.add_argument("--label", default="")
    ap.add_argument("--src")
    ap.add_argument("--dir-csv")
    ap.add_argument("--group-csv")
    ap.add_argument("--fail-csv")
    ap.add_argument("--sig-csv")
    ap.add_argument("--baseline")
    ap.add_argument("--control-junit", help="JUnit of the MySQL control; prints the comparable pass rate")
    ap.add_argument("--compare-csv", help="per-directory comparable pass rate vs --control-junit")
    a = ap.parse_args()

    cases = list(iter_cases(a.junit))
    tot = collections.Counter(c["status"] for c in cases)
    n = len(cases)
    ran = n - tot["skipped"]
    print(
        f"{a.label or a.junit}: tests={n} pass={tot['pass']} failure={tot['failure']} "
        f"error={tot['error']} skipped={tot['skipped']} warnings={sum(c['warning'] for c in cases)} "
        f"pass_rate={100.0 * tot['pass'] / n if n else 0:.2f}% "
        f"pass_rate_excl_skipped={100.0 * tot['pass'] / ran if ran else 0:.2f}% "
        f"test_seconds={sum(c['time'] for c in cases):.1f}"
    )

    if a.control_junit:
        ctl = list(iter_cases(a.control_junit))
        ctl_pass = {(c["class"], c["name"]): test_dir(c["file"]) for c in ctl if c["status"] == "pass"}
        here_pass = {(c["class"], c["name"]) for c in cases if c["status"] == "pass"}
        here_all = {(c["class"], c["name"]) for c in cases}
        ok = sum(1 for k in ctl_pass if k in here_pass)
        print(
            f"comparable: control_passing={len(ctl_pass)} also_passing_here={ok} "
            f"comparable_pass_rate={100.0 * ok / len(ctl_pass) if ctl_pass else 0:.2f}% "
            f"(test ids missing here: {sum(1 for k in ctl_pass if k not in here_all)})"
        )
        if a.compare_csv:
            per = collections.defaultdict(lambda: [0, 0])
            for k, d in ctl_pass.items():
                per[d][0] += 1
                per[d][1] += 1 if k in here_pass else 0
            with open(a.compare_csv, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["directory", "control_passing", "also_passing", "comparable_pass_rate_pct"])
                for d in sorted(per, key=lambda x: (-per[x][0], x)):
                    w.writerow([d, per[d][0], per[d][1], f"{100.0 * per[d][1] / per[d][0]:.2f}"])

    if a.dir_csv:
        write_counts(a.dir_csv, "directory", counts_table(cases, lambda c: [test_dir(c["file"])]))
    if a.group_csv:
        write_counts(a.group_csv, "group", counts_table(cases, lambda c: groups_for(c["file"], a.src, c["class"]) or ["(none)"]))

    baseline = set()
    if a.baseline and os.path.exists(a.baseline):
        with open(a.baseline) as fh:
            for row in csv.DictReader(fh):
                baseline.add(row["test"])

    bad = [c for c in cases if c["status"] in ("failure", "error")]
    for c in bad:
        c["tid"] = f"{c['class']}::{c['name']}"
        c["bucket"] = "harness/environment" if c["tid"] in baseline else triage(c["message"])
        c["sig"] = signature(c["message"])
    # Fixture failures (wpSetUpBeforeClass) print their database error once, so
    # later tests of the same class fail without a database error of their own.
    # bucket_inferred: an 'unknown' test inherits the most common direct bucket
    # of its class, when the class has one.
    per_class = collections.defaultdict(collections.Counter)
    for c in bad:
        if c["bucket"] != "unknown":
            per_class[c["class"]][c["bucket"]] += 1
    for c in bad:
        c["bucket_inferred"] = c["bucket"]
        if c["bucket"] == "unknown" and per_class[c["class"]]:
            c["bucket_inferred"] = per_class[c["class"]].most_common(1)[0][0]
    if a.fail_csv:
        with open(a.fail_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["test", "directory", "status", "bucket", "bucket_inferred", "signature"])
            for c in bad:
                w.writerow([c["tid"], test_dir(c["file"]), c["status"], c["bucket"], c["bucket_inferred"], c["sig"]])
    if bad:
        direct = collections.Counter(c["bucket"] for c in bad)
        inferred = collections.Counter(c["bucket_inferred"] for c in bad)
        print("buckets (direct): " + ", ".join(f"{k}={v}" for k, v in direct.most_common()))
        print("buckets (class-inferred): " + ", ".join(f"{k}={v}" for k, v in inferred.most_common()))
    if a.sig_csv:
        sigs = collections.OrderedDict()
        for c in bad:
            e = sigs.setdefault((c["bucket"], c["sig"]), {"count": 0, "examples": []})
            e["count"] += 1
            if len(e["examples"]) < 3:
                e["examples"].append(c["tid"])
        with open(a.sig_csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["bucket", "rank_in_bucket", "count", "signature", "example_tests"])
            by_bucket = collections.defaultdict(list)
            for (bucket, sig), e in sigs.items():
                by_bucket[bucket].append((e["count"], sig, e["examples"]))
            for bucket in sorted(by_bucket):
                for i, (n, sig, ex) in enumerate(sorted(by_bucket[bucket], key=lambda x: -x[0]), 1):
                    w.writerow([bucket, i, n, sig, " | ".join(ex)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
