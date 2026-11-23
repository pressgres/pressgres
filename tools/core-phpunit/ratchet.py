#!/usr/bin/env python3
"""Regression ratchet for the core PHPUnit suite on PostgreSQL (I-010, ADR-0006).

The gate is a committed list of test IDs that must keep passing
(baseline/expected-pass.txt), not a pass-rate threshold. `check` fails when:

  1. the bootstrap did not reach PHPUnit (no JUnit file, unparseable, 0 tests);
  2. the JUnit test count dropped by more than --max-count-drop-pct (default 1 %)
     against baseline/baseline.json (data-provider or fatal collapse);
  3. any expected test is no longer passing (failure, error, skipped or missing).

Newly passing tests never fail the check; they are listed so the baseline can
be updated in the same pull request (`update`). The comparable pass rate
against the MySQL control (baseline/mysql-control-pass.txt) is reported as a
trend only.

Subcommands:
  check  JUNIT [--phpunit-log LOG] [--summary-md PATH] [--csv PATH] [--out-dir DIR]
  update JUNIT [JUNIT ...] [--merge]   rewrite expected-pass.txt (+ baseline.json)
  passing JUNIT [JUNIT ...] --out PATH  write the passing IDs (intersection) to PATH

Test IDs are `Class::name` exactly as PHPUnit writes them in JUnit (data-set
names included). Backslash, newline and carriage return are escaped so every ID
is one line. An ID that occurs more than once (the restapi-autosave testsuite
re-runs some tests) passes only if every occurrence passes.

Standard library only.
"""
import argparse
import collections
import csv
import datetime
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE_DIR = os.path.join(HERE, "baseline")
DEFAULT_EXPECTED = os.path.join(BASELINE_DIR, "expected-pass.txt")
DEFAULT_META = os.path.join(BASELINE_DIR, "baseline.json")
DEFAULT_CONTROL = os.path.join(BASELINE_DIR, "mysql-control-pass.txt")
DEFAULT_FLAKY = os.path.join(BASELINE_DIR, "flaky.txt")

LIST_LIMIT_MD = 100
_XML_INVALID = re.compile("[^\u0009\u000a\u000d\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


class BootstrapError(Exception):
    """The JUnit log is missing, unreadable or empty."""


def escape_id(text):
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def load_tree(path):
    try:
        return ET.parse(path)
    except ET.ParseError:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8", errors="replace")
        return ET.ElementTree(ET.fromstring(_XML_INVALID.sub("\ufffd", text)))


def read_junit(path):
    """Return (counts Counter, {test_id: status}) for one JUnit file.

    Status per ID is the worst over its occurrences: error > failure >
    skipped > pass.
    """
    if not path or not os.path.isfile(path):
        raise BootstrapError(f"JUnit file not found: {path} (PHPUnit did not finish or never started)")
    if os.path.getsize(path) == 0:
        raise BootstrapError(f"JUnit file is empty: {path}")
    try:
        tree = load_tree(path)
    except ET.ParseError as exc:
        raise BootstrapError(f"JUnit file is not valid XML: {path}: {exc}") from exc
    rank = {"pass": 0, "skipped": 1, "failure": 2, "error": 3}
    counts = collections.Counter()
    status = {}
    for tc in tree.iter("testcase"):
        st = "pass"
        for child in tc:
            if child.tag in ("failure", "error"):
                st = child.tag
                break
            if child.tag == "skipped":
                st = "skipped"
        counts[st] += 1
        counts["tests"] += 1
        tid = escape_id(f"{tc.get('class') or tc.get('classname') or ''}::{tc.get('name') or ''}")
        if tid not in status or rank[st] > rank[status[tid]]:
            status[tid] = st
    if counts["tests"] == 0:
        raise BootstrapError(f"JUnit file contains 0 tests: {path} (bootstrap did not reach PHPUnit)")
    return counts, status


def passing(status):
    return {t for t, s in status.items() if s == "pass"}


def read_list(path):
    if not path or not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        return {ln.rstrip("\n") for ln in fh if ln.strip() and not ln.startswith("#")}


def write_list(path, ids):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for t in sorted(ids):
            fh.write(t + "\n")


def read_meta(path):
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def pct(num, den):
    return round(100.0 * num / den, 2) if den else 0.0


def fmt_delta(value, base, unit=""):
    if base is None:
        return "n/a"
    d = value - base
    if isinstance(d, float):
        return f"{d:+.2f}{unit}"
    return f"{d:+d}{unit}"


def bootstrap_hint(log_path):
    """Last lines of the PHPUnit console log, to show why bootstrap failed."""
    if not log_path or not os.path.isfile(log_path):
        return ""
    with open(log_path, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().splitlines()
    return "\n".join(ln if len(ln) <= 400 else ln[:400] + " …" for ln in lines[-20:])


def evaluate(junit, expected, meta, control, flaky, max_drop_pct, phpunit_log=None):
    """Compute the ratchet result. Returns a dict; result['ok'] is the verdict."""
    res = {"junit": junit, "problems": [], "ok": True}
    try:
        counts, status = read_junit(junit)
    except BootstrapError as exc:
        res.update(ok=False, bootstrap=False, counts=collections.Counter(), status={})
        res["problems"].append(f"bootstrap: {exc}")
        res["log_tail"] = bootstrap_hint(phpunit_log)
        return res
    res["bootstrap"] = True
    res["counts"] = counts
    res["status"] = status
    here_pass = passing(status)

    base_tests = meta.get("tests")
    res["base_tests"] = base_tests
    if base_tests:
        floor = base_tests * (1 - max_drop_pct / 100.0)
        res["count_floor"] = floor
        if counts["tests"] < floor:
            res["ok"] = False
            res["problems"].append(
                f"test count: {counts['tests']} JUnit tests is more than {max_drop_pct:g}% below the baseline "
                f"{base_tests} (floor {floor:.0f})"
            )

    regressions = sorted(t for t in expected - flaky if t not in here_pass)
    res["regressions"] = [(t, status.get(t, "missing")) for t in regressions]
    if regressions:
        res["ok"] = False
        res["problems"].append(f"regressions: {len(regressions)} expected-pass test(s) no longer pass")
    res["newly_passing"] = sorted(here_pass - expected - flaky)
    res["flaky_passing"] = len(flaky & here_pass)
    res["flaky_total"] = len(flaky)

    res["pass_rate"] = pct(counts["pass"], counts["tests"])
    if control:
        res["control_total"] = len(control)
        res["comparable_pass"] = len(control & here_pass)
        res["comparable_pass_rate"] = pct(res["comparable_pass"], len(control))
    return res


def render_text(res, meta):
    out = []
    c = res["counts"]
    if res["bootstrap"]:
        out.append(
            f"tests={c['tests']} pass={c['pass']} failure={c['failure']} error={c['error']} "
            f"skipped={c['skipped']} pass_rate={res['pass_rate']:.2f}%"
        )
        if "comparable_pass_rate" in res:
            out.append(
                f"comparable_pass_rate={res['comparable_pass_rate']:.2f}% "
                f"({res['comparable_pass']}/{res['control_total']} MySQL-control-passing IDs; "
                f"baseline {meta.get('comparable_pass_rate', 'n/a')}%)"
            )
        out.append(
            f"expected-pass regressions={len(res['regressions'])} newly_passing={len(res['newly_passing'])} "
            f"flaky_passing={res['flaky_passing']}/{res['flaky_total']}"
        )
        for t, st in res["regressions"]:
            out.append(f"REGRESSION [{st}] {t}")
        for t in res["newly_passing"]:
            out.append(f"NEWLY PASSING {t}")
    for p in res["problems"]:
        out.append(f"FAIL {p}")
    if res.get("log_tail"):
        out.append("--- phpunit.log (tail) ---")
        out.append(res["log_tail"])
    if res["bootstrap"] and res["newly_passing"]:
        out.append(UPDATE_HINT_TEXT)
    out.append("RATCHET: PASS" if res["ok"] else "RATCHET: FAIL")
    return "\n".join(out)


UPDATE_HINT_TEXT = (
    "To ratchet the baseline in this PR: download the run artifact and copy "
    "expected-pass.candidate.txt and baseline.candidate.json to tools/core-phpunit/baseline/ "
    "(expected-pass.txt, baseline.json), or run locally: "
    "python3 tools/core-phpunit/ratchet.py update tools/core-phpunit/results/<label>/junit.xml"
)


def md_list(items, limit=LIST_LIMIT_MD):
    lines = [f"- {t}" for t in items[:limit]]
    if len(items) > limit:
        lines.append(f"- … {len(items) - limit} more (see the artifact)")
    return "\n".join(lines)


def render_md(res, meta, title):
    c = res["counts"]
    verdict = "PASS" if res["ok"] else "FAIL"
    md = [f"## {title}: ratchet {verdict}", ""]
    if not res["bootstrap"]:
        md += ["**The bootstrap did not reach PHPUnit.**", ""]
        md += [f"- {p}" for p in res["problems"]]
        if res.get("log_tail"):
            md += ["", "```text", res["log_tail"], "```"]
        return "\n".join(md) + "\n"
    b = meta
    rows = [
        ("Tests (JUnit)", c["tests"], b.get("tests")),
        ("Pass", c["pass"], b.get("pass")),
        ("Failure", c["failure"], b.get("failure")),
        ("Error", c["error"], b.get("error")),
        ("Skipped", c["skipped"], b.get("skipped")),
    ]
    md += ["| Metric | This run | Baseline | Delta |", "|---|---:|---:|---:|"]
    for name, v, base in rows:
        md.append(f"| {name} | {v} | {base if base is not None else 'n/a'} | {fmt_delta(v, base)} |")
    md.append(
        f"| Pass rate | {res['pass_rate']:.2f} % | {b.get('pass_rate', 'n/a')} % | "
        f"{fmt_delta(res['pass_rate'], b.get('pass_rate'), ' pp')} |"
    )
    if "comparable_pass_rate" in res:
        md.append(
            f"| **Comparable pass rate** (vs MySQL control, {res['control_total']} IDs) | "
            f"**{res['comparable_pass_rate']:.2f} %** | {b.get('comparable_pass_rate', 'n/a')} % | "
            f"{fmt_delta(res['comparable_pass_rate'], b.get('comparable_pass_rate'), ' pp')} |"
        )
    md += [
        "",
        f"Expected-pass list: {len(res['regressions'])} regression(s), "
        f"{len(res['newly_passing'])} newly passing, flaky passing {res['flaky_passing']}/{res['flaky_total']}. "
        "The comparable pass rate is a published trend; the ratchet is the gate (ADR-0006).",
        "",
    ]
    if res["problems"]:
        md += ["### Failures", ""] + [f"- {p}" for p in res["problems"]] + [""]
    if res["regressions"]:
        md += ["### Regressions (expected to pass)", "", md_list([f"`{t}` ({st})" for t, st in res["regressions"]]), ""]
    if res["newly_passing"]:
        md += [
            "### Newly passing",
            "",
            md_list([f"`{t}`" for t in res["newly_passing"]]),
            "",
            "Ratchet the baseline in this PR: download the `core-phpunit-pgsql` artifact and copy "
            "`expected-pass.candidate.txt` → `tools/core-phpunit/baseline/expected-pass.txt` and "
            "`baseline.candidate.json` → `tools/core-phpunit/baseline/baseline.json`, or run "
            "`python3 tools/core-phpunit/ratchet.py update <junit.xml>` locally.",
            "",
        ]
    return "\n".join(md) + "\n"


def write_csv(path, res, meta, label):
    c = res["counts"]
    new = not os.path.exists(path)
    with open(path, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow([
                "label", "utc", "git_sha", "bootstrap", "tests", "pass", "failure", "error", "skipped",
                "pass_rate_pct", "comparable_pass_rate_pct", "baseline_comparable_pass_rate_pct",
                "regressions", "newly_passing", "ratchet",
            ])
        w.writerow([
            label, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            os.environ.get("GITHUB_SHA", ""), int(res["bootstrap"]), c["tests"], c["pass"], c["failure"],
            c["error"], c["skipped"], f"{res.get('pass_rate', 0.0):.2f}",
            f"{res['comparable_pass_rate']:.2f}" if "comparable_pass_rate" in res else "",
            meta.get("comparable_pass_rate", ""), len(res.get("regressions", [])),
            len(res.get("newly_passing", [])), "pass" if res["ok"] else "fail",
        ])


def build_meta(counts, here_pass, control, previous, extra=None):
    meta = dict(previous)
    meta.update({
        "tests": counts["tests"],
        "pass": counts["pass"],
        "failure": counts["failure"],
        "error": counts["error"],
        "skipped": counts["skipped"],
        "pass_rate": pct(counts["pass"], counts["tests"]),
        "expected_pass": len(here_pass),
    })
    if control:
        meta["comparable_pass_rate"] = pct(len(control & here_pass), len(control))
        meta["control_passing"] = len(control)
    if extra:
        meta.update(extra)
    return meta


def cmd_check(a):
    expected = read_list(a.expected)
    if not expected and not a.allow_empty_expected:
        print(f"expected-pass list missing or empty: {a.expected}", file=sys.stderr)
        return 2
    meta = read_meta(a.meta)
    control = read_list(a.control)
    flaky = read_list(a.flaky)
    res = evaluate(a.junit, expected, meta, control, flaky, a.max_count_drop_pct, a.phpunit_log)
    print(render_text(res, meta))
    if a.summary_md:
        with open(a.summary_md, "a", encoding="utf-8") as fh:
            fh.write(render_md(res, meta, a.title))
    if a.csv:
        write_csv(a.csv, res, meta, a.label)
    if a.out_dir and res["bootstrap"]:
        os.makedirs(a.out_dir, exist_ok=True)
        write_list(os.path.join(a.out_dir, "newly-passing.txt"), res["newly_passing"])
        with open(os.path.join(a.out_dir, "regressions.txt"), "w", encoding="utf-8") as fh:
            for t, st in res["regressions"]:
                fh.write(f"{st}\t{t}\n")
        cand = passing(res["status"]) - flaky
        write_list(os.path.join(a.out_dir, "expected-pass.candidate.txt"), cand)
        with open(os.path.join(a.out_dir, "baseline.candidate.json"), "w", encoding="utf-8") as fh:
            json.dump(build_meta(res["counts"], cand, control, meta, {
                "generated_utc": utc_now(),
                "generated_from": f"ratchet.py check (single run{run_ref()}); review newly passing IDs before committing",
            }), fh, indent=2, sort_keys=True)
            fh.write("\n")
    return 0 if res["ok"] else 1


def run_ref():
    if os.environ.get("GITHUB_RUN_ID"):
        return f", GitHub run {os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    return ""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def intersect_runs(junits):
    """Passing IDs common to all runs, the first run's counts, and IDs that differ."""
    sets, first_counts = [], None
    for j in junits:
        counts, status = read_junit(j)
        first_counts = first_counts or counts
        sets.append(passing(status))
    common = set.intersection(*sets)
    unstable = set.union(*sets) - common
    return first_counts, common, unstable


def cmd_update(a):
    counts, common, unstable = intersect_runs(a.junit)
    flaky = read_list(a.flaky)
    if unstable:
        print(f"{len(unstable)} test(s) pass in some runs but not all; left out of expected-pass:")
        for t in sorted(unstable):
            print(f"  UNSTABLE {t}")
    new = common - flaky
    old = read_list(a.expected)
    if a.merge:
        new |= old
    write_list(a.expected, new)
    control = read_list(a.control)
    meta = build_meta(counts, new, control, read_meta(a.meta), {"generated_utc": utc_now()})
    with open(a.meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"expected-pass: {len(old)} -> {len(new)} (+{len(new - old)} / -{len(old - new)}); wrote {a.expected} and {a.meta}")
    return 0


def cmd_passing(a):
    _, common, unstable = intersect_runs(a.junit)
    write_list(a.out, common)
    print(f"{len(common)} passing IDs written to {a.out} ({len(unstable)} differ between runs)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--expected", default=DEFAULT_EXPECTED)
    ap.add_argument("--meta", default=DEFAULT_META)
    ap.add_argument("--control", default=DEFAULT_CONTROL, help="MySQL control passing IDs (comparable pass rate)")
    ap.add_argument("--flaky", default=DEFAULT_FLAKY, help="IDs ignored by the ratchet in both directions")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check")
    c.add_argument("junit")
    c.add_argument("--phpunit-log")
    c.add_argument("--summary-md", help="append a Markdown summary (e.g. $GITHUB_STEP_SUMMARY)")
    c.add_argument("--csv", help="append one summary row")
    c.add_argument("--out-dir", help="write newly-passing.txt, regressions.txt and candidate baseline files")
    c.add_argument("--label", default="pgsql-C")
    c.add_argument("--title", default="Core PHPUnit on PostgreSQL 18 (PG-C)")
    c.add_argument("--max-count-drop-pct", type=float, default=1.0)
    c.add_argument("--allow-empty-expected", action="store_true")
    c.set_defaults(func=cmd_check)

    u = sub.add_parser("update")
    u.add_argument("junit", nargs="+")
    u.add_argument("--merge", action="store_true", help="keep IDs already in the list (only add)")
    u.set_defaults(func=cmd_update)

    p = sub.add_parser("passing")
    p.add_argument("junit", nargs="+")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_passing)

    a = ap.parse_args(argv)
    try:
        return a.func(a)
    except BootstrapError as exc:
        print(f"FAIL bootstrap: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
