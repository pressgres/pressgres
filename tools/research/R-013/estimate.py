"""Build a scenario inventory and a release-diff footprint from pinned audits."""

import argparse
from collections import Counter, defaultdict
import csv
from difflib import SequenceMatcher
from functools import lru_cache
import math
from pathlib import Path
import re

from sample import read_csv, source_lines


WP = "wordpress-develop-7.1.5"
GB = "gutenberg-89408c2"
TIERS = ("low", "expected", "high")
UPGRADE = "src/wp-admin/includes/upgrade.php"
SCHEMA = "src/wp-admin/includes/schema.php"
DB = "src/wp-includes/class-wpdb.php"


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def coords(source):
    path, _, number = source.rpartition(":")
    repo, _, name = path.partition("/")
    return repo, name, int(number)


def network_only(path):
    name = path.rsplit("/", 1)[-1]
    return (
        path.startswith(("src/wp-admin/network/", "src/wp-admin/network.php"))
        or name.startswith("ms-")
        or name in {"ms.php", "class-wp-site.php", "class-wp-site-query.php",
                    "class-wp-network.php", "class-wp-network-query.php"}
        or name in {"wp-activate.php", "wp-signup.php"}
    )


def legacy(path):
    return path.rsplit("/", 1)[-1] in {
        "xmlrpc.php", "class-wp-xmlrpc-server.php", "deprecated.php", "pluggable-deprecated.php",
    }


def historic(name):
    return bool(re.fullmatch(r"upgrade_\d+.*", name))


def eligible_php(row, tier):
    path, func = row["file"], row["function"]
    return (
        row["entity"] != "sites/blogs" and not network_only(path)
        and not (path == UPGRADE and historic(func))
        and func not in {"upgrade_network", "wp_install_network"}
        and not (tier == "low" and legacy(path))
        and path != DB
    )


def php_candidate(row, tier):
    if row["identity"] != "identity" or not eligible_php(row, tier):
        return False
    kind, pattern = row["kind"], row["pattern"]
    if tier == "low" and row["confidence"] != "high":
        return False
    if kind in {"cast", "validation", "type-decl"}:
        return True
    if kind == "sql-format":
        return "implicit" not in pattern or tier == "high"
    if kind == "sentinel":
        return bool(re.search(r"(?<!\w)(?:0|-1)(?!\w)|SQL zero", pattern)) or tier == "high"
    if kind == "other":
        if tier == "high":
            return True
        return bool(re.search(r"insert_id|ordering|sprintf|printf|declaration", pattern))
    return tier == "high" and kind == "query-var"


def php_category(path, line):
    if "/rest-api" in path:
        return "REST PHP"
    if path == SCHEMA and line <= 336:
        return "Schema integration"
    if path in {SCHEMA, UPGRADE, "src/wp-admin/install.php", "src/wp-admin/upgrade.php"}:
        return "Install/seed/upgrade"
    return "Core PHP"


def sites_for(root, sibling, reviewed, tier):
    data = lambda issue, name: sibling / issue / "docs/research/data" / f"{issue}-{name}.csv"
    sites = {}
    unmapped = set()

    def add(repo, path, line, category, origin):
        assert 1 <= line <= len(source_lines(root / repo / path)), (repo, path, line)
        site = (repo, path, line)
        if site in sites:
            old_category, origins = sites[site]
            # REST callers outside the REST subtree take the REST category.
            if category != old_category:
                assert "REST PHP" in {category, old_category}, (site, category, old_category)
                sites[site] = ("REST PHP", origins)
            origins.add(origin)
        else:
            sites[site] = (category, {origin})

    @lru_cache(maxsize=None)
    def block_mapping(path):
        slug = Path(path).stem
        gb_path = f"packages/block-library/src/{slug}/index.php"
        if not (root / GB / gb_path).is_file():
            return gb_path, {}
        wp_lines = source_lines(root / WP / path)
        gb_lines = source_lines(root / GB / gb_path)
        mapping = {}
        for a, b, size in SequenceMatcher(None, wp_lines, gb_lines, autojunk=False).get_matching_blocks():
            for i in range(size):
                mapping[a+i+1] = b+i+1
        return gb_path, mapping

    def add_php(path, line, origin):
        if path.startswith("src/wp-includes/blocks/"):
            gb_path, mapping = block_mapping(path)
            if line in mapping:
                add(GB, gb_path, mapping[line], "Gutenberg PHP", origin)
            else:
                unmapped.add((path, line))
        else:
            add(WP, path, line, php_category(path, line), origin)

    for row in read_csv(data("R-001", "php-id-hits")):
        if php_candidate(row, tier):
            # Only the explicit schema integration points below ship in core.
            if row["file"] == SCHEMA and int(row["line"]) <= 336:
                continue
            add_php(row["file"], int(row["line"]), "R-001 classified")

    for row in read_csv(data("R-012", "rest-hits")):
        if row["severity"] == "breaks-with-uuid" or (
            tier != "low" and row["severity"] == "degrades" and
            (tier == "high" or "rest_get_route" not in row["evidence"])
        ):
            repo, path, line = coords(row["source"])
            add(repo, path, line, "REST PHP", "R-012 REST")

    for row in read_csv(data("R-012", "js-hits")):
        if row["severity"] == "cosmetic":
            continue
        if tier == "low" and row["confidence"] != "high":
            continue
        if tier == "expected" and (
            row["confidence"] == "low" or
            (row["severity"] != "breaks-with-uuid" and row["kind"] == "type")
        ):
            continue
        repo, path, line = coords(row["source"])
        category = "Block metadata" if path.endswith("block.json") else "Gutenberg JS/TS"
        add(repo, path, line, category, "R-012 Gutenberg")

    for row in read_csv(data("R-002", "ddl-paths")):
        if not row["file"].endswith("/" + UPGRADE) or historic(row["function"]):
            continue
        fresh = row["function"] in {"wp_install", "wp_install_defaults"} and row["identity_sensitive"] == "yes"
        upgraded = row["function"] in {"wp_upgrade", "make_db_current_silent", "make_db_current"}
        if fresh or upgraded:
            repo, path, line = coords(f"{row['file']}:{row['line']}")
            if not (row["function"] == "wp_install_defaults" and line >= 457):
                add(repo, path, line, "Install/seed/upgrade", "R-002 DDL/DML")

    # Insert/DML anchors in R-002 are supplemented by the legacy seed
    # references and the entry points where an integration would replace DDL.
    manual = {
        UPGRADE: (63, 186, 207, 212, 268, 342, 367, 386, 413, 676, 677, 678),
        SCHEMA: (36, 430, 455, 475),
        "src/wp-admin/install.php": (442,),
        "src/wp-settings.php": (220,),
        "package.json": (10, 11),
    }
    for path, numbers in manual.items():
        for number in numbers:
            category = "Build pin" if path == "package.json" else php_category(path, number)
            add(WP, path, number, category, "Source-reviewed integration anchor")

    legacy_js = {
        "src/js/_enqueues/vendor/plupload/wp-plupload.js": 130,
        "src/js/_enqueues/vendor/plupload/handlers.js": 479,
    }
    if tier != "low":
        legacy_js["src/js/_enqueues/vendor/tinymce/plugins/wpeditimage/plugin.js"] = 282
    for path, number in legacy_js.items():
        add(WP, path, number, "Classic admin JS", "Source-reviewed attachment ID parser")

    known = set(sites)
    review_sites = {}
    for row in reviewed:
        if row["classification"] == "edit" and eligible_php(row, tier):
            before = set(sites)
            add_php(row["file"], int(row["line"]), "R-013 reviewed edit")
            new = set(sites) - before
            assert len(new) <= 1
            review_sites[row["sample"]] = next(iter(new), None)
    return sites, len(unmapped), known, review_sites


def cluster(numbers, gap=7):
    groups = []
    for number in sorted(set(numbers)):
        if groups and number - groups[-1][1] <= gap:
            groups[-1] = (groups[-1][0], number)
        else:
            groups.append((number, number))
    return groups


def footprint(sites):
    paths = defaultdict(list)
    for repo, path, line in sites:
        paths[repo, path].append(line)
    return paths


def wilson(matches, size):
    z = 1.95996398454
    p = matches / size
    center = (p + z*z / (2*size)) / (1 + z*z/size)
    half = z * math.sqrt(p*(1-p)/size + z*z/(4*size*size)) / (1 + z*z/size)
    return center - half, p, center + half


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("sibling_root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    reviewed = read_csv(args.output / "R-013-ambiguous-sample.csv")
    sample_count = Counter(row["classification"] for row in reviewed)
    print(sample_count)
    for key, value in (("edit", sample_count["edit"]), ("identity-related", 80 - sample_count["no"])):
        print(key, value, tuple(round(1847*p, 1) for p in wilson(value, 80)))

    ranges = []
    for i, tier in enumerate(TIERS):
        sites, unmapped, known, review_sites = sites_for(args.reference, args.sibling_root, reviewed, tier)
        named, base = footprint(sites), footprint(known)
        keys = sorted(sites)
        print(tier, "unmapped Gutenberg PHP:", unmapped)
        write_csv(args.output / f"R-013-sites-{tier}.csv", [
            dict(repo=repo, path=path, line=line, source=f"{repo}/{path}:{line}",
                 category=sites[repo, path, line][0],
                 evidence=" | ".join(sorted(sites[repo, path, line][1])))
            for repo, path, line in keys
        ])

        for category, count in sorted(Counter(sites[key][0] for key in keys).items()):
            print(tier, category, count)

        novel = [site for site in review_sites.values() if site]
        projected_lines = max(len(novel), round(1847 * wilson(len(novel), 80)[i]))
        unknown = projected_lines - len(novel)
        hunk_count = lambda paths: sum(len(cluster(lines)) for lines in paths.values())
        # Rates reflect the locations of the reviewed additions. New-file
        # growth is capped by the candidate universe and shrunk for repeated
        # observations within a file. Hunk growth also allows shared context.
        eligible_paths = {
            row["file"] for row in read_csv(
                args.sibling_root / "R-001/docs/research/data/R-001-php-id-hits.csv"
            )
            if row["identity"] == "ambiguous" and eligible_php(row, tier)
            and not row["file"].startswith("src/wp-includes/blocks/")
        }
        new_files = len(named.keys() - base.keys())
        new_hunks = max(0, hunk_count(named) - hunk_count(base))
        file_factor = (0.25, 0.5, 0.75)[i]
        hunk_factor = (0.6, 0.8, 1.0)[i]
        extra_files = min(
            len(eligible_paths - {path for repo, path in named if repo == WP}),
            round(unknown * new_files / max(1, len(novel)) * file_factor),
        )
        extra_hunks = round(unknown * new_hunks / max(1, len(novel)) * hunk_factor)
        # Helpers (PHP/JS) and the native SQL manifest are net additions.
        php_helpers, js_helpers, sql_lines = [(120, 60, 150), (220, 110, 190), (380, 180, 260)][i]
        helper_files = (3, 4, 6)[i]
        ranges.append(dict(
            tier=tier, named_lines=len(sites), named_files=len(named), named_hunks=hunk_count(named),
            sampled_novel_edits=len(novel), sampled_file_delta=new_files, sampled_hunk_delta=new_hunks,
            projected_extra_lines=unknown, projected_extra_files=extra_files, projected_extra_hunks=extra_hunks,
            upstream_lines=len(sites)+unknown, upstream_files=len(named)+extra_files,
            upstream_hunks=hunk_count(named)+extra_hunks,
            php_helper_lines=php_helpers, js_helper_lines=js_helpers, native_schema_lines=sql_lines,
            new_files_and_hunks=helper_files, total_files=len(named)+extra_files+helper_files,
            total_hunks=hunk_count(named)+extra_hunks+helper_files,
        ))
    write_csv(args.output / "R-013-size.csv", ranges)
    for row in ranges:
        print(row)


if __name__ == "__main__":
    main()
