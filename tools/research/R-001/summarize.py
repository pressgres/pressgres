#!/usr/bin/env python3
"""Reproduce the R-001 counts, rankings and deterministic manual sample frame."""
import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scan import ENTITIES

KINDS = ("cast", "validation", "sql-format", "sentinel", "type-decl", "query-var",
         "cache-key", "other")
SITE = "sites/blogs"


def location(row):
    return row["file"], int(row["line"])


def ranking(rows, by_function):
    counts = Counter()
    first = {}
    for row in rows:
        name = (row["file"], row["function"]) if by_function else (row["file"],)
        counts[name] += 1
        first[name] = min(first.get(name, int(row["line"])), int(row["line"]))
    return [(name, first[name], count) for name, count in
            sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:30]]


def report(rows, prefix):
    identities = [row for row in rows if row["identity"] == "identity"]
    scope = [row for row in identities if row["entity"] != SITE]
    direct_kinds = {"cast", "validation", "sql-format", "sentinel", "type-decl"}
    direct = [row for row in scope if row["kind"] in direct_kinds or
              row["pattern"].startswith(("wpdb insert_id", "ID arithmetic"))]
    likely = [row for row in direct if row["kind"] != "sentinel" or
              row["pattern"].startswith("SQL zero") or row["pattern"].endswith((" 0", " -0", " -1"))]
    # insert_id's producer and reset operations are shared across tables.
    likely += [row for row in rows if row["file"].endswith("/class-wpdb.php") and
               row["pattern"].startswith(("wpdb insert_id", "mysqli_insert_id"))]
    print("Rows", len(rows), Counter(row["identity"] for row in rows))
    print("Identity confidences", Counter(row["confidence"] for row in identities))
    print("In-scope rows / unique source lines / direct review lines",
          len(scope), len({location(row) for row in scope}), len({location(row) for row in direct}))
    print("Likely patch source lines, including shared insert_id driver lines",
          len({location(row) for row in likely}))
    print("Identity source lines (all domains)", len({location(row) for row in identities}))
    by_entity = Counter((row["entity"], row["kind"]) for row in identities)
    print()
    print("| Entity | " + " | ".join(KINDS) + " | Total |")
    print("|" + " --- |" * (len(KINDS) + 2))
    for entity in (*ENTITIES, "Total"):
        counts = [by_entity[entity, kind] if entity != "Total" else
                  sum(by_entity[domain, kind] for domain in ENTITIES) for kind in KINDS]
        print("| " + " | ".join(map(str, (entity, *counts, sum(counts)))) + " |")
    print()
    for label, predicate in (
        ("PHP explicit zero", lambda pattern: pattern.startswith("ID ") and pattern.endswith((" 0", " -0"))),
        ("PHP explicit -1", lambda pattern: pattern.startswith("ID ") and pattern.endswith(" -1")),
        ("SQL zero predicates/defaults", lambda pattern: pattern.startswith("SQL zero")),
        ("PHP false/null/empty/presence/truthiness", lambda pattern: not pattern.startswith("SQL zero") and
         not (pattern.startswith("ID ") and pattern.endswith((" 0", " -0", " -1")))),
    ):
        subset = [row for row in identities if row["kind"] == "sentinel" and predicate(row["pattern"])]
        print(label, len(subset), Counter(row["entity"] for row in subset))
    for pattern in ("wpdb insert_id", "REST integer schema", "REST numeric route", "get_*_id",
                    "int parameter", "int return", "SQL zero", "wpdb field_types"):
        subset = [row for row in rows if row["pattern"].startswith(pattern)]
        print(pattern, len(subset), Counter(row["identity"] for row in subset))
    print()
    print("| Rank | File and first classified line | Hits | Function and first classified line | Hits |")
    print("| --- | --- | ---: | --- | ---: |")
    for index, (file, function) in enumerate(zip(ranking(identities, False), ranking(identities, True)), 1):
        ((file_name,), file_line, file_count) = file
        ((fn_file, fn_name), fn_line, fn_count) = function
        print(f"| {index} | `{prefix}/{file_name}:{file_line}` | {file_count} | "
              f"`{fn_name}` at `{prefix}/{fn_file}:{fn_line}` | {fn_count} |")


def sample(rows):
    strata = defaultdict(list)
    for row in rows:
        label = row["identity"]
        strata[row["kind"] if label == "identity" else label].append(row)
    rng = random.Random(1001)
    for group in (*KINDS, "ambiguous", "non-identity numeric"):
        for row in rng.sample(strata[group], min(8, len(strata[group]))):
            yield {"stratum": group, **row}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--sample", action="store_true", help="emit review sample frame as CSV")
    parser.add_argument("--prefix", default="wordpress-develop-7.1.5", help="path prefix for report citations")
    args = parser.parse_args()
    with args.csv.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if args.sample:
        candidates = list(sample(rows))
        writer = csv.DictWriter(sys.stdout, fieldnames=list(candidates[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)
    else:
        report(rows, args.prefix)


if __name__ == "__main__":
    main()
