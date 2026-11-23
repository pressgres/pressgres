"""Calculate R-013 engineering effort scenarios from the two-layer churn CSV."""

import argparse
from collections import defaultdict
from datetime import date
import math
from pathlib import Path
from statistics import median

from estimate import TIERS, WP, write_csv
from sample import read_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="R-013 CSV directory")
    args = parser.parse_args()
    layers = defaultdict(list)
    for row in read_csv(args.output / "R-013-churn.csv"):
        if row["latest_lane"] == "1":
            layers[row["kind"], row["base"], row["target"]].append(row)
    pins = {
        row["tag"]: date.fromisoformat(row["wp_commit_date"][:10])
        for row in read_csv(args.output / "R-013-release-pins.csv")
    }
    end = pins["7.1.5"]
    start = date(end.year-1, end.month, end.day)
    observations = defaultdict(list)
    point_count = 0
    confirmed_security = 0
    for (kind, _, target), rows in layers.items():
        assert len(rows) == 2
        counts = tuple(sum(int(row[key]) for row in rows) for key in ("overlap_3", "uncertain_3"))
        observations[kind].append(counts)
        if kind == "point" and start < pins[target] <= end:
            point_count += 1
            confirmed_security += any(
                row["layer"] == WP and bool(row["security_evidence"]) for row in rows
            )
    print(f"Latest lane {start} < date <= {end}: {point_count} point tags, "
          f"{confirmed_security} tags have explicit security evidence")

    assumptions = [
        # Fixed days: minor, routine point, security. Variable hours: exact, uncertain.
        (3, 0.5, 1, 0.5, 0.15, min),
        (5, 1.25, 1.5, 1, 0.35, median),
        (8, 2, 2.5, 1.5, 0.6, max),
    ]
    results = []
    for tier, (minor, point, security, exact, uncertain, stat) in zip(TIERS, assumptions, strict=True):
        minor_exact, minor_uncertain = map(stat, zip(*observations["minor-shipped-base"]))
        point_exact, point_uncertain = map(stat, zip(*observations["point"]))
        minor_days = math.ceil(minor + (minor_exact*exact + minor_uncertain*uncertain)/8)
        point_hours = point_exact*exact + point_uncertain*uncertain
        point_days = math.ceil(2*(point + point_hours/8))/2
        security_days = math.ceil(2*(security + point_hours/8))/2
        annual = 3*minor_days + point_count*security_days
        results.append(dict(
            tier=tier, minor_exact=minor_exact, minor_uncertain=minor_uncertain,
            point_exact=point_exact, point_uncertain=point_uncertain,
            fixed_minor_days=minor, fixed_point_days=point, fixed_security_days=security,
            hours_per_exact=exact, hours_per_uncertain=uncertain,
            days_per_minor=minor_days, days_per_point=point_days, days_per_security=security_days,
            minors_per_year=3, points_last_year=point_count, confirmed_security_last_year=confirmed_security,
            annual_days_at_security_rate=annual, annual_fte_at_220_days=round(annual/220, 3),
            annual_days_with_25pct_reserve=annual*1.25,
        ))
    write_csv(args.output / "R-013-effort.csv", results)


if __name__ == "__main__":
    main()
