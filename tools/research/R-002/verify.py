#!/usr/bin/env python3
"""Compare the CSV to SQL emitted by the pinned WordPress schema function."""

import argparse
import csv
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

PHP_FIXTURE = """
function is_multisite() { return false; }
$wpdb = new class {
    public function get_charset_collate() {
        return 'DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci';
    }
    public function __get($name) { return 'fixture_' . $name; }
};
require $argv[1];
echo json_encode([wp_get_db_schema('all'), wp_get_db_schema('ms_global')], JSON_THROW_ON_ERROR);
"""


def extract_tables(sql):
    tables = {}
    for statement in sql.split(";"):
        if not statement.strip():
            continue
        header, *definitions, footer = statement.strip().splitlines()
        assert footer.startswith(") DEFAULT CHARACTER SET utf8mb4")
        table = re.fullmatch(r"CREATE TABLE fixture_(\w+) \(", header)[1]
        tables[table] = [line.strip().rstrip(",") for line in definitions]
    return tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("columns", type=Path)
    args = parser.parse_args()
    schema = args.reference / "src/wp-admin/includes/schema.php"
    run = subprocess.run(["php", "-r", PHP_FIXTURE, str(schema)],
                         check=True, capture_output=True, text=True)
    single_site, network = map(extract_tables, json.loads(run.stdout))
    assert set(network) == {"blogs", "blogmeta", "registration_log", "site", "sitemeta", "signups"}
    assert not (set(single_site) & set(network))

    columns = defaultdict(list)
    with args.columns.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            columns[row["table"]].append(row)
    assert set(columns) == set(single_site)
    for table, definitions in single_site.items():
        fields = [line for line in definitions if line.split()[0] not in {"PRIMARY", "UNIQUE", "KEY"}]
        keys = set(definitions) - set(fields)
        normalized_keys = {" ".join(key.split()) for key in keys}
        csv_keys = set()
        assert len(columns[table]) == len(fields)
        for column, field in zip(columns[table], fields):
            expected = f"{column['column']} {column['mysql_type']}"
            if column["nullable"] == "no":
                expected += " NOT NULL"
            if column["class"] == "identity-pk":
                expected += " auto_increment"
            if column["default"]:
                expected += f" default {column['default']}"
            assert field == expected, (table, field, expected)
            recorded = {key.partition(" @ ")[0] for key in column["keys"].split(" | ") if key}
            # Split on the index's outer opening parenthesis, then drop each optional subpart.
            memberships = {
                key for key in normalized_keys
                if column["column"] in [part.partition("(")[0] for part in key.split("(", 1)[1][:-1].split(",")]
            }
            assert memberships == recorded, (table, column["column"], memberships, recorded)
            csv_keys.update(recorded)
        assert csv_keys == normalized_keys
    print(f"Matched {len(single_site)} single-site tables, {sum(map(len, columns.values()))} "
          f"columns and all key memberships; confirmed {len(network)} network-only tables.")


if __name__ == "__main__":
    main()
