"""Measure touched-path churn and old-side proximity in scratch Git mirrors."""

import argparse
from collections import defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess

from estimate import GB, WP, cluster, footprint, write_csv
from sample import read_csv


TAG = re.compile(r"(6\.8|6\.9|7\.0|7\.1)\.\d+$")
PIN = {WP: "7.1.5", GB: "89408c2b9bd944575dfa9039bc6870da1c8f56cb"}
HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
# Explicit evidence in the sibling R-005 security retrospective citations.
KNOWN_SECURITY = {"6.9.2", "6.9.3"}


def git(repo, *args, input_text=None, lazy=True):
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "0" if lazy else "1"}
    return subprocess.run(
        ["git", "-C", str(repo), "--literal-pathspecs", *args],
        input=input_text, stdout=subprocess.PIPE, check=True, text=True, env=env,
        encoding="utf-8", errors="replace",
    ).stdout


def trees(repo, ref, paths):
    result = {}
    for entry in git(repo, "ls-tree", "-r", "-z", ref, "--", *paths).split("\0"):
        if entry:
            head, name = entry.split("\t")
            _, kind, oid = head.split()
            if kind == "blob":
                result[name] = oid
    return result


def prefetch(repo, oids):
    if not oids:
        return
    names = "\n".join(sorted(set(oids))) + "\n"
    missing = [line.split()[0] for line in git(
        repo, "cat-file", "--batch-check=%(objectname)", input_text=names, lazy=False
    ).splitlines() if line.endswith(" missing")]
    if missing:
        git(repo, "-c", "fetch.negotiationAlgorithm=noop", "fetch", "--no-tags", "--no-write-fetch-head", "--filter=blob:none",
            "origin", "--stdin", input_text="\n".join(missing) + "\n")


def json_blobs(repo, oids):
    oids = sorted(set(oids))
    prefetch(repo, oids)
    output = git(repo, "show", *oids, lazy=False)
    decoder = json.JSONDecoder()
    items = {}
    for oid in oids:
        value, end = decoder.raw_decode(output.lstrip())
        items[oid] = value
        output = output.lstrip()[end:]
    assert not output.strip()
    return items


def wp_packages(package):
    return {
        key.removeprefix("@wordpress/"): version
        for group in ("dependencies", "devDependencies")
        for key, version in package.get(group, {}).items() if key.startswith("@wordpress/")
    }


def releases(wp, gb, package_names):
    ending = git(wp, "show", "-s", "--format=%cI", PIN[WP]).strip()
    listing = git(wp, "for-each-ref", "--format=%(refname:short) %(committerdate:iso-strict) %(objectname)",
                  "refs/tags").splitlines()
    tags = {}
    for line in listing:
        tag, *rest = line.split()
        if TAG.fullmatch(tag) and datetime.fromisoformat(rest[0]).date() <= datetime.fromisoformat(ending).date():
            tags[tag] = rest
    tags = dict(sorted(tags.items(), key=lambda t: tuple(map(int, t[0].split(".")))))
    tag_trees = {tag: trees(wp, tag, ["package.json"])["package.json"] for tag in tags}
    manifests = json_blobs(wp, tag_trees.values())
    wp_manifests = {tag: manifests[tag_trees[tag]] for tag in tags}
    historical = {tag: wp_packages(package) for tag, package in wp_manifests.items() if not package.get("gutenberg")}
    commits = {}
    for branch, since in [("6.8", "2025-02-01"), ("6.9", "2025-09-01")]:
        commits[branch] = git(
            gb, "log", "--first-parent", "--format=%H %cI", "--grep=chore(release): publish",
            f"--since={since}", f"--until={ending}", f"refs/heads/wp/{branch}",
        ).splitlines()

    all_packages = set().union(*(set(v) for v in historical.values()))
    files = {f"packages/{p}/package.json" for p in all_packages}
    published = {
        sha: trees(gb, sha, sorted(files))
        for values in commits.values() for sha, _ in (value.split() for value in values)
    }
    gb_blobs = json_blobs(gb, (oid for inventory in published.values() for oid in inventory.values()))
    result = {}
    for tag, (stamp, sha) in tags.items():
        manifest = wp_manifests[tag]
        pinned = manifest.get("gutenberg", {}).get("sha")
        pinned = git(gb, "rev-parse", f"{pinned}^{{commit}}").strip() if pinned else None
        row = dict(tag=tag, wp_commit=sha, wp_commit_date=stamp, gb_commit=pinned or "",
                   gb_basis="direct pin" if pinned else "unavailable",
                   matched_packages="", package_count="", audited_package_mismatches="",
                   package_mismatches="")
        if not pinned:
            target = historical[tag]
            branch = tag.rsplit(".", 1)[0]
            candidates = []
            for choice in commits[branch]:
                commit, date = choice.split()
                if datetime.fromisoformat(date) > datetime.fromisoformat(stamp):
                    continue
                got = {
                    Path(path).parent.name: gb_blobs[oid]["version"]
                    for path, oid in published[commit].items()
                }
                wrong = {key for key in target if target[key] != got.get(key)}
                # Package names in the path and npm name can diverge. Keep
                # mismatches visible, and rank the audited packages first.
                candidates.append((len(wrong & package_names), len(wrong), date, commit, sorted(wrong)))
            mismatch, count, _, commit, names = min(
                candidates, key=lambda item: (item[0], item[1], -datetime.fromisoformat(item[2]).timestamp())
            )
            row.update(
                gb_commit=commit, gb_basis="inferred package publish snapshot",
                matched_packages=len(target)-count, package_count=len(target),
                audited_package_mismatches=mismatch, package_mismatches=" | ".join(names),
            )
        result[tag] = row
    return result


def diff(repo, old, new, paths):
    if old == new or not paths:
        return {}, {}
    output = git(
        repo, "-c", "core.quotePath=false", "diff", "--no-ext-diff", "--no-textconv",
        "--no-renames", "--unified=0", "--no-color", "--numstat", "--patch", old, new,
        "--", *paths, lazy=False,
    )
    stats = {}
    hunks = defaultdict(list)
    current = None
    for line in output.split("\n"):
        if line.startswith("diff --git a/"):
            left, right = line.removeprefix("diff --git a/").rsplit(" b/", 1)
            assert left == right
            current = left
        elif current is None and line.count("\t") >= 2:
            added, deleted, name = line.split("\t", 2)
            stats[name] = (int(added), int(deleted)) if added != "-" else (0, 0)
        elif match := HEADER.match(line):
            a, n, b, m = match.groups()
            hunks[current].append((int(a), int(n or 1), int(b), int(m or 1)))
    assert set(hunks) <= set(stats), (old, new, set(hunks) - set(stats))
    return stats, hunks


def projection(line, hunks):
    """Return the inclusive range in the historical tree and its uncertainty."""
    delta = 0
    for old, n, new, m in hunks:
        if n == 0:
            if line <= old:
                break
        elif line < old:
            break
        elif line < old+n:
            return (new, new+m-1, False) if m else (new, new+1, False)
        delta += m-n
    return line+delta, line+delta, True


def proximity(sites, mapping, changes):
    counts = {}
    projected = {line: projection(line, mapping) for line in sites}
    for distance in (0, 3, 10):
        exact = uncertain = 0
        for start, end in cluster(sites):
            points = [point for line, point in projected.items() if start <= line <= end]
            # Measure from actual sites rather than from intervening context.
            hits = {
                precise for left, right, precise in points
                for a, n, _, _ in changes
                if (a if not n else a+n-1) >= left-distance and a <= right+distance
            }
            exact += True in hits
            uncertain += bool(hits) and True not in hits
        counts[f"overlap_{distance}"] = exact
        counts[f"uncertain_{distance}"] = uncertain
    return counts


def transitions(tags):
    by_branch = defaultdict(list)
    for tag in tags:
        by_branch[tag.rsplit(".", 1)[0]].append(tag)
    def active(tag):
        date = datetime.fromisoformat(tags[tag]["wp_commit_date"])
        return all(
            date < datetime.fromisoformat(row["wp_commit_date"])
            for other, row in tags.items()
            if other.endswith(".0") and tuple(map(int, other.split("."))) > tuple(map(int, tag.split(".")))
        )
    for branch in by_branch.values():
        for old, new in zip(branch, branch[1:]):
            yield old, new, "point", active(new)
    latest = [tag for tag in tags if tag.endswith(".0") or active(tag)]
    latest.sort(key=lambda tag: tags[tag]["wp_commit_date"])
    for old, new in zip(latest, latest[1:]):
        if new.endswith(".0"):
            yield old, new, "minor-shipped-base", True
    launches = [tag for tag in tags if tag.endswith(".0")]
    for old, new in zip(launches, launches[1:]):
        yield old, new, "minor-launch-base", False
    yield "7.1.0", "7.1.5", "point-cumulative", False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="directory containing both pinned checkouts")
    parser.add_argument("scratch", type=Path, help="directory with wp.git and gb.git from step 3")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if Path("/tmp").resolve() not in args.scratch.resolve().parents:
        parser.error("use a dedicated scratch directory under /tmp for the Git fetches")
    repositories = {WP: args.scratch / "wp.git", GB: args.scratch / "gb.git"}
    for name, repo in repositories.items():
        assert git(repo, "rev-parse", PIN[name]).strip() == git(
            args.reference / name, "rev-parse", "HEAD", lazy=False
        ).strip()
    sites = read_csv(args.output / "R-013-sites-expected.csv")
    paths = footprint((row["repo"], row["path"], int(row["line"])) for row in sites)
    package_names = {path.split("/")[1] for name, path in paths if name == GB}
    tags = releases(repositories[WP], repositories[GB], package_names)
    write_csv(args.output / "R-013-release-pins.csv", list(tags.values()))
    comparisons = list(transitions(tags))
    security_evidence = {}
    for old, new, kind, _ in comparisons:
        if kind == "point":
            commits = git(
                repositories[WP], "log", "--format=%H", "--regexp-ignore-case",
                "--grep=^Security: Backport the WordPress .* security fixes", f"{old}..{new}",
            ).splitlines()
            evidence = commits + (["R-005 retrospective"] if new in KNOWN_SECURITY else [])
            security_evidence[old, new] = " | ".join(evidence)
    rows = []
    detail = []
    for name, repo in repositories.items():
        print("Measuring", name, flush=True)
        selected = sorted(path for layer, path in paths if layer == name)
        field = "wp_commit" if name == WP else "gb_commit"
        refs = {tag: row[field] for tag, row in tags.items()}
        history = {ref: trees(repo, ref, selected) for ref in set(refs.values())}
        prefetch(repo, (oid for inventory in history.values() for oid in inventory.values()))
        mappings = {}
        for old_tag, new_tag, kind, active in comparisons:
            old, new = refs[old_tag], refs[new_tag]
            mismatches = {
                package.strip()
                for tag in (old_tag, new_tag)
                for package in tags[tag]["package_mismatches"].split("|") if package.strip()
            }
            measured = [path for path in selected if name != GB or path.split("/")[1] not in mismatches]
            stats, hunks = diff(repo, old, new, measured)
            if old not in mappings:
                mappings[old] = diff(repo, PIN[name], old, selected)[1]
            mapping = mappings[old]
            aggregate = dict(
                layer=name, base=old_tag, target=new_tag, kind=kind, latest_lane=int(active),
                security_evidence=security_evidence.get((old_tag, new_tag), "") if kind == "point" else "",
                base_commit=old, target_commit=new, files_in_footprint=len(selected),
                files_measured=len(measured), paths_without_package_match=len(selected)-len(measured),
                base_present=len(history[old]), target_present=len(history[new]), files_changed=len(stats),
                added=sum(a for a, _ in stats.values()), deleted=sum(d for _, d in stats.values()),
                changed_files_without_base=sum(path not in history[old] for path in stats),
                unmapped_hunks=sum(len(cluster(paths[name, path])) for path in stats if path not in history[old]),
                **{f"{prefix}_{gap}": 0 for prefix in ("overlap", "uncertain") for gap in (0, 3, 10)},
            )
            assert len(stats) == sum(history[old].get(p) != history[new].get(p) for p in measured)
            for path, (added, deleted) in stats.items():
                counts = (proximity(paths[name, path], mapping.get(path, []), hunks.get(path, []))
                          if path in history[old] else {k: 0 for k in aggregate if k.startswith(("overlap_", "uncertain_"))})
                for key, value in counts.items():
                    aggregate[key] += value
                detail.append(dict(layer=name, base=old_tag, target=new_tag, kind=kind, path=path,
                                   added=added, deleted=deleted, base_path_present=int(path in history[old]), **counts))
            rows.append(aggregate)
    write_csv(args.output / "R-013-churn.csv", rows)
    write_csv(args.output / "R-013-churn-files.csv", detail)


if __name__ == "__main__":
    main()
