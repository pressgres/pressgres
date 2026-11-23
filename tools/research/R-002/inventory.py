#!/usr/bin/env python3
"""Inventory the pinned WordPress 7.1.5 src tree without loading WordPress."""

import argparse
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = "src/wp-admin/includes/schema.php"
UPGRADE = "src/wp-admin/includes/upgrade.php"
WPDB = "src/wp-includes/class-wpdb.php"
HELPER = "src/wp-admin/install-helper.php"

# Resolved by reading the core callers. A composite key retains its FK roles.
REFERENCES = {
    "termmeta.term_id": ("terms.term_id", "src/wp-includes/taxonomy.php", 1408, ""),
    "term_taxonomy.term_id": ("terms.term_id", "src/wp-includes/taxonomy.php", 2652, ""),
    "term_taxonomy.parent": ("terms.term_id", "src/wp-includes/taxonomy.php", 2133,
                             "Parent term in the same taxonomy"),
    "term_relationships.object_id": ("posts.ID or links.link_id or registered object type",
                                     "src/wp-admin/includes/bookmark.php", 287,
                                     "Polymorphic member of composite PK; no generated default; zero is invalid"),
    "term_relationships.term_taxonomy_id": ("term_taxonomy.term_taxonomy_id",
                                            "src/wp-includes/taxonomy.php", 2923,
                                            "FK member of composite PK; no generated default; zero is invalid"),
    "commentmeta.comment_id": ("comments.comment_ID", "src/wp-includes/comment.php", 529, ""),
    "comments.comment_post_ID": ("posts.ID (all post types); absent permitted",
                                 "src/wp-includes/comment.php", 2884,
                                 "Requested polymorphic bucket; core resolves a single table"),
    "comments.comment_parent": ("comments.comment_ID", "src/wp-includes/comment.php", 2420, ""),
    "comments.user_id": ("users.ID", "src/wp-includes/comment.php", 4117, "Anonymous author allowed"),
    "links.link_owner": ("users.ID", "src/wp-admin/includes/bookmark.php", 212,
                         "Replace default 1 with explicit actor or NULL; map legacy 1 to its actual user"),
    "postmeta.post_id": ("posts.ID", "src/wp-includes/post.php", 2697, ""),
    "posts.post_author": ("users.ID", "src/wp-includes/post.php", 4824, ""),
    "posts.post_parent": ("posts.ID", "src/wp-includes/post.php", 4846, ""),
    "usermeta.user_id": ("users.ID", "src/wp-includes/user.php", 1246, ""),
}
POLYMORPHIC = {"term_relationships.object_id", "comments.comment_post_ID"}
DDL_PATTERN = re.compile(
    r"\b(?:ALTER\s+TABLE|CREATE\s+(?:TABLE|DATABASE|INDEX)|"
    r"DROP\s+(?:TABLE|INDEX)|RENAME\s+TABLE|TRUNCATE\s+TABLE)\b", re.I
)
FUNCTION = re.compile(r"^\s*(?:(?:public|protected|private|static)\s+)*function\s+([\w]+)\s*\(")
QUERY_ALTER = re.compile(r"""\$wpdb->query\s*\(\s*['"]ALTER\s+TABLE\b""", re.I)


def cite(path, line):
    return f"wordpress-develop-7.1.5/{path}:{line}"


def schema_rows(files):
    rows = []
    tables = []
    table = None
    for number, raw in enumerate(files[SCHEMA].splitlines(), 1):
        start = re.search(r"CREATE TABLE \$wpdb->(\w+) \(", raw)
        if start:
            table = start[1]
            scope = ("single-site" if number < 210 or table == "usermeta" else "multisite")
            tables.append((number, table, scope, [], []))
        elif table and raw.startswith(")"):
            table = None
        elif table:
            definition = raw.strip().rstrip(",").replace("$max_index_length", "191")
            if re.match(r"(?:PRIMARY|UNIQUE|KEY)\b", definition):
                tables[-1][4].append((number, re.sub(r" +", " ", definition)))
            else:
                tables[-1][3].append((number, definition))

    for _, table, scope, columns, keys in tables:
        if scope != "single-site":
            continue
        for line, definition in columns:
            match = re.fullmatch(
                r"(\w+) (\w+(?:\(\d+\))?(?: unsigned)?)(.*)", definition
            )
            assert match, (line, definition)
            column, mysql_type, attrs = match.groups()
            assert re.fullmatch(r"(?: NOT NULL)?(?: auto_increment| default (?:'[^']*'|NULL|\d+))?", attrs)
            default = attrs.partition(" default ")[2]
            memberships = [
                f"{key} @ {cite(SCHEMA, key_line)}" for key_line, key in keys
                if re.search(rf"(?<=[(,]){re.escape(column)}(?=[(,)])", key)
            ]
            name = f"{table}.{column}"
            notes = [cite(SCHEMA, line)]
            ref = ""
            if name in REFERENCES:
                ref, source, source_line, detail = REFERENCES[name]
                notes.append(cite(source, source_line))
                if detail:
                    notes.append(detail)
                kind = "identity-polymorphic" if name in POLYMORPHIC else "identity-fk"
                pg = "uuid NOT NULL" if table == "term_relationships" else "uuid NULL"
                if default in {"0", "'0'"} and table != "term_relationships":
                    notes.append("Legacy zero maps to SQL NULL")
            elif "auto_increment" in attrs:
                assert any(key.startswith("PRIMARY KEY") for key in memberships)
                kind, pg = "identity-pk", "uuid NOT NULL DEFAULT uuidv7()"
                notes.append("MySQL AUTO_INCREMENT")
            elif mysql_type == "datetime":
                kind, pg = "datetime", "timestamp(0) without time zone"
                notes.append("Proposed zero-date to NULL policy requires caller review")
            elif "int" in mysql_type:
                kind, pg = "non-identity-numeric", "bigint" if mysql_type.startswith("bigint") else "integer"
                if name == "terms.term_group":
                    notes.append("Numeric alias group token, not a row reference; "
                                 + cite("src/wp-includes/taxonomy.php", 2537))
            elif "text" in mysql_type or mysql_type.startswith("varchar"):
                kind = "text"
                pg = mysql_type if mysql_type.startswith("varchar") else "text"
            else:
                kind, pg = "other", ""
            rows.append((table, column, mysql_type, "no" if "NOT NULL" in attrs else "yes",
                         default, " | ".join(memberships), kind, ref, pg,
                         "yes" if column != column.lower() else "no", "; ".join(notes)))
    assert set(REFERENCES) <= {f"{row[0]}.{row[1]}" for row in rows}
    return tables, rows


def raw_ddl(files):
    for path, content in files.items():
        function = "(file scope)"
        for number, source in enumerate(content.splitlines(), 1):
            declaration = FUNCTION.match(source)
            if declaration:
                function = declaration[1]
            if DDL_PATTERN.search(source):
                yield path, number, function, source.strip()


def facade(files):
    declarations = re.findall(
        r"^\s*(public|protected|private)\s+(?:function\s+(\w+)|\$(\w+))",
        files[WPDB], re.M
    )
    observed = defaultdict(dict)
    for path, content in files.items():
        if path == WPDB:
            continue
        for line, source in enumerate(content.splitlines(), 1):
            if source.lstrip().startswith(("*", "//", "#")):
                continue
            for match in re.finditer(r"\$wpdb->(\w+)(\s*\()?", source):
                name, call = match.groups()
                observed[name, bool(call)].setdefault(path, line)
    for access, method, prop in declarations:
        name = method or prop
        hits = observed[name, bool(method)]
        if hits:
            print(f"{access:9} {'method' if method else 'property':8} {name:28} "
                  f"{', '.join(cite(p, n) for p, n in list(hits.items())[:2])}")


def read_reviews(path):
    with path.open() as stream:
        for line in stream:
            if line.startswith("#") or not line.strip():
                continue
            tag, source, number, function, kind, tables, sensitive, notes = line.rstrip("\n").split("\t")
            yield tag, (source, int(number), function, kind, tables, sensitive, notes)


def write_csv(path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header.split(","))
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="Root containing WordPress src/")
    parser.add_argument("--output", type=Path, help="Existing directory for both CSVs")
    parser.add_argument("--candidates", action="store_true", help="Print raw DDL keyword hits for audit")
    parser.add_argument("--facade", action="store_true", help="Print named wpdb declarations with observed uses")
    args = parser.parse_args()
    paths = sorted((args.reference / "src").rglob("*.php"))
    files = {str(p.relative_to(args.reference)): p.read_text(encoding="utf-8", errors="replace")
             for p in paths}
    tables, columns = schema_rows(files)
    reviewed = list(read_reviews(Path(__file__).with_name("sql-review.tsv")))
    accepted = [(SCHEMA, line, "wp_get_db_schema", "CREATE TABLE", table, "yes",
                 f"{scope} definition; see schema column inventory or multisite section")
                for line, table, scope, _, _ in tables]
    excluded = set()
    for tag, row in reviewed:
        source, line, *_ = row
        assert 1 <= line <= len(files[source].splitlines()), row
        if tag == "exclude":
            excluded.add((source, line))
        else:
            assert tag == "include", row
            accepted.append(row)

    candidates = list(raw_ddl(files))
    if args.candidates:
        for path, line, function, source in candidates:
            print(f"{cite(path, line)}\t{function}\t{source}")
    covered = {(row[0], row[1]) for row in accepted} | excluded
    for path, line, function, source in candidates:
        if (path, line) in covered:
            continue
        assert path == UPGRADE and QUERY_ALTER.search(source) or (
            path == UPGRADE and re.search(r"""\$wpdb->query\( 'DROP TABLE IF EXISTS '""", source)
        ) or path == "src/wp-includes/ms-site.php" and line == 835, (path, line, source)
        literal = re.split(r"""\$wpdb->query\( ['"]""", source, maxsplit=1)[1]
        if literal.startswith("DROP TABLE IF EXISTS '"):
            table = literal.split("'")[2]
            sql = f"DROP TABLE IF EXISTS <prefix>{table}"
        else:
            sql = literal.split('"', 1)[0]
            table_token = re.match(r"(?:ALTER TABLE|DROP TABLE IF EXISTS) (\S+)", sql)[1]
            table = re.sub(r"^\{?\$wpdb->|\}$", "", table_token.strip("`"))
        # Reviewed rule applied to direct literals only; generic identifiers are context dependent.
        identity = ("context" if table.startswith("$") else
                    "yes" if re.search(r"\b(?:PRIMARY KEY|(?:blog|site|meta|signup|option)_id|ID|post_category|unsigned)\b",
                                       sql, re.I) or sql.startswith("DROP TABLE") else "no")
        accepted.append((path, line, function, "ALTER TABLE" if sql.startswith("ALTER") else "DROP TABLE",
                         table, identity, sql))
    accepted.sort(key=lambda row: (row[0], row[1], row[3]))
    assert len({(r[0], r[1], r[3]) for r in accepted}) == len(accepted)

    if args.output:
        write_csv(args.output / "R-002-columns.csv",
                  "table,column,mysql_type,nullable,default,keys,class,references,pg_type_proposed,needs_quoting,notes",
                  columns)
        write_csv(args.output / "R-002-ddl-paths.csv",
                  "file,line,function,statement_kind,tables,identity_sensitive,notes",
                  [(cite(path, line).rsplit(":", 1)[0], line, *rest) for path, line, *rest in accepted])
    if args.facade:
        facade(files)

    for scope in ("single-site", "multisite"):
        group = [(table, len(cols), len(keys)) for _, table, label, cols, keys in tables if label == scope]
        print(scope, group)
    print("columns", len(columns), dict(Counter(row[6] for row in columns)))
    print("mixed-case columns", sum(row[9] == "yes" for row in columns))
    print("zero-date defaults", sum(row[4] == "'0000-00-00 00:00:00'" for row in columns))
    print("PHP files", len(files), "raw DDL hits", len(candidates),
          "rejected keyword hits", len(excluded),
          "literal wpdb ALTER sites", sum(bool(QUERY_ALTER.search(row[3])) for row in candidates))
    print("SQL paths", len(accepted), dict(Counter(row[3] for row in accepted)))


if __name__ == "__main__":
    main()
