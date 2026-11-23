"""Draw the fixed-seed R-001 review frame and validate the reviewed sample."""

import argparse
import csv
from functools import lru_cache
from pathlib import Path
import random


SEED = 13013
SIZE = 80
LABELS = {"no", "review", "edit", "out-of-scope", "unresolved"}


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def frame(hits, root):
    rows = [
        (index, row) for index, row in enumerate(read_csv(hits), 1)
        if row["identity"] == "ambiguous"
    ]
    assert len(rows) == 1847, len(rows)
    return [
        {"sample": str(number), "hit_row": str(index),
         "source": f"{root.name}/{row['file']}:{row['line']}", **row}
        for number, (index, row) in enumerate(random.Random(SEED).sample(rows, SIZE), 1)
    ]


@lru_cache(maxsize=None)
def source_lines(path):
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="pinned WordPress checkout")
    parser.add_argument("hits", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--context", action="store_true")
    args = parser.parse_args()
    rows = frame(args.hits, args.reference)
    reviews = read_csv(args.review) if args.review else []
    if args.review:
        assert len(reviews) == SIZE
    for i, row in enumerate(rows):
        lines = source_lines(args.reference / row["file"])
        number = int(row["line"])
        assert row["snippet"] in lines[number - 1].strip(), row
        if args.review:
            review = reviews[i]
            assert all(review[k] == v for k, v in row.items()), review
            assert review["classification"] in LABELS and review["reason"], review
            assert review["confidence_review"] in {"high", "medium", "low"}, review
        if not args.review or args.context:
            print(row["sample"], row["source"], row["function"], row["kind"], row["pattern"])
        if args.context:
            for index in range(max(1, number - 4), min(len(lines), number + 4) + 1):
                print(f"{index:4} {'>' if index == number else ' '} {lines[index-1]}")


if __name__ == "__main__":
    main()
