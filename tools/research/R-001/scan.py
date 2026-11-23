#!/usr/bin/env python3
"""Token-based candidate inventory for pinned WordPress PHP. Requires PHP CLI."""
import argparse
import csv
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

COLUMNS = "file line function pattern entity kind identity confidence snippet".split()
ENTITIES = (
    "posts", "users", "comments", "terms", "term_taxonomy", "meta",
    "options", "links", "sites/blogs",
)
UNKNOWN = ("ambiguous", "low")
NUMERIC = ("non-identity numeric", "medium")
EXCLUDED = {
    "simplepie", "phpmailer", "requests", "id3", "getid3", "sodium_compat",
    "random_compat", "pomo", "text", "ixr", "php-ai-client", "php-compat",
    "atomlib.php", "class-ixr.php", "class-avif-info.php", "class-json.php",
    "class-phpass.php", "class-pop3.php", "class-snoopy.php",
}
# ID-bearing WP_Query arguments. Name/slug variants and numeric range controls
# are intentionally absent.
QUERY = {
    "p": "posts", "attachment_id": "posts", "page_id": "posts",
    "post_parent": "posts", "post_parent__in": "posts", "post_parent__not_in": "posts",
    "post__in": "posts", "post__not_in": "posts",
    "author": "users", "author__in": "users", "author__not_in": "users",
    "cat": "terms", "category": "terms", "category__in": "terms",
    "category__not_in": "terms", "category__and": "terms",
    "tag_id": "terms", "tag__in": "terms", "tag__not_in": "terms", "tag__and": "terms",
}
# Distinct domains trump the surrounding controller/table (e.g. comment_post_ID).
FIELDS = {
    "post_author": "users", "post_parent": "posts", "comment_parent": "comments",
    "comment_post_id": "posts", "link_owner": "users", "parent_post": "posts",
    "parent_page": "posts", "cat_id": "terms", "catid": "terms",
    "thumbnail_id": "posts", "sticky_posts": "posts", "page_on_front": "posts",
    "page_for_posts": "posts", "page_for_privacy_policy": "posts",
    "object_id": "ambiguous", "insert_id": "ambiguous", "meta_id": "meta",
    "default_category": "terms", "default_link_category": "terms",
    "post_category": "terms", "_thumbnail_id": "posts", "default_term_id": "terms",
    "attachment": "posts", "postid": "posts", "userid": "users", "commentid": "comments",
    "parent_id": "ambiguous", "tt_ids": "term_taxonomy", "cat_tt_id": "term_taxonomy",
    "mid": "meta", "post_thumbnail": "posts", "menu_item_parent": "posts",
    "menu_item_db_id": "posts", "db_id": "posts", "trackback_id": "comments",
    "the_id": "posts", "all_page_ids": "posts", "tax_id": "terms",
}
PREFIXES = {
    "post": "posts", "page": "posts", "attachment": "posts", "revision": "posts",
    "menu_item": "posts", "autosave": "posts", "font_family": "posts",
    "font_face": "posts", "product": "posts", "user": "users", "author": "users",
    "comment": "comments", "term": "terms", "tag": "terms", "cat": "terms",
    "category": "terms", "nav_menu": "terms", "menu": "terms",
    "term_taxonomy": "term_taxonomy", "tt": "term_taxonomy",
    "meta": "meta", "umeta": "meta", "option": "options", "link": "links",
    "site": "sites/blogs", "blog": "sites/blogs", "network": "sites/blogs",
}
ID_SUFFIX = re.compile(r"([a-z][a-z_]*)_(?:ids?|id_list)$", re.I)
NUMERIC_NAME = re.compile(
    r"(?:^|_)(?:count|counts|size|width|height|length|offset|limit|order|"
    r"priority|timestamp|time|timeout|ttl|year|month|monthnum|day|hour|minute|second|paged|number|"
    r"per_page|index|status|version|version_added|seconds|port|position|"
    r"bytes|columns|rows|spacing|weight|depth|duration|level|quality)(?:_|$)"
)
NON_ENTITY_ID = re.compile(
    r"(?:widget|sidebar|session|style|script|filter|plugin|request|handle|"
    r"screen|control|section|instance|transaction|variation|provider|model|"
    r"block|client|field|css|element|template_part_area)_?ids?$"
)
CACHE_GROUPS = {
    "posts": "posts", "post_meta": "posts", "post-queries": None,
    "users": "users", "user_meta": "users", "userlogins": None,
    "useremail": None, "userslugs": None, "comments": "comments",
    "comment_meta": "comments", "terms": "terms", "term_meta": "terms",
    "bookmark": "links", "sites": "sites/blogs", "networks": "sites/blogs",
    "blog_meta": "sites/blogs", "site_meta": "sites/blogs",
    "blog-details": "sites/blogs", "site-details": "sites/blogs",
}
SQL_TABLES = {
    "posts": "posts", "users": "users", "comments": "comments", "terms": "terms",
    "term_taxonomy": "term_taxonomy", "term_relationships": "ambiguous",
    "postmeta": "meta", "usermeta": "meta", "commentmeta": "meta", "termmeta": "meta",
    "options": "options", "links": "links", "blogs": "sites/blogs",
    "site": "sites/blogs", "sitemeta": "sites/blogs", "blogmeta": "sites/blogs",
    "signups": "sites/blogs", "registration_log": "sites/blogs",
}
INT_FORMAT = re.compile(r"(?<!%)(?:%%)*(%((\d+)\$)?[-+0-9.' #]*d)\b")
PRINTF_FORMAT = re.compile(r"%(?:%|(?:(\d+)\$)?[-+0-9.' #]*([sdfFiuxXobcgeEG]))")
SQL_START = re.compile(r"\b(?:SELECT\b.+?\bFROM|UPDATE\s+\S+\s+SET|DELETE\s+FROM|INSERT\s+(?:IGNORE\s+)?INTO|ALTER\s+TABLE|CREATE\s+TABLE)\b", re.I | re.S)
COMPARISONS = {"===", "!==", "==", "!=", "<>", "<", ">", ">=", "<=", "<=>"}
NAME_TOKEN = re.compile(r"^(?:\$|\\)?[A-Za-z_]\w*$")


def source_files(root):
    paths = set((root / "src").glob("wp-*.php"))
    paths.add(root / "src/xmlrpc.php")
    for subtree in ("wp-admin", "wp-includes"):
        paths.update((root / "src" / subtree).rglob("*.php"))
    return sorted(paths, key=lambda path: path.as_posix())


def quoted(value):
    return len(value) >= 2 and value[0] in "'\"" and value[0] == value[-1]


def bare(value):
    return value.strip("'\"`$").lower()


def name_entity(value):
    name = bare(value)
    if name in FIELDS:
        return FIELDS[name]
    if name in {"postids", "userids", "commentids", "termid", "menuid", "blogid", "siteid"}:
        return PREFIXES[name.split("id")[0]]
    if NON_ENTITY_ID.search(name):
        return None
    normalized = re.sub(r"^(?:(?:old|new|current|original|queried|target|default|"
                        r"source|dest|latest|previous|next|parent|child|primary|"
                        r"existing|updated|deleted|selected|excluded|requested|"
                        r"found|valid|invalid|translated|termmeta)_)+", "", name)
    if normalized in FIELDS:
        return FIELDS[normalized]
    if name == "id" or name == "ids" or normalized in {"id", "ids"}:
        return "ambiguous"
    if name in ("term_taxonomy_id", "term_taxonomy_ids"):
        return "term_taxonomy"
    match = ID_SUFFIX.search(normalized)
    if match:
        prefix = match[1].rstrip("_")
        for part in sorted(PREFIXES, key=len, reverse=True):
            if prefix == part or prefix.endswith("_" + part):
                return PREFIXES[part]
        return "ambiguous"
    if name.endswith("_id") or name.endswith("_ids"):
        return "ambiguous"
    return None


def domain_from_context(file):
    stem = file.stem.replace("_", "-")
    # Ordered exceptions for contexts where a generic id refers to another type.
    for marker, entity in (
        ("term-taxonomy", "term_taxonomy"), ("menu-items", "posts"),
        ("nav-menu", "terms"), ("menus-controller", "terms"),
        ("user-request", "posts"), ("application-password", "users"),
        ("post-tags", "terms"), ("taxonomy", "terms"), ("categor", "terms"),
        ("tags", "terms"), ("-terms", "terms"), ("term", "terms"),
        ("comment", "comments"), ("author", "users"), ("user", "users"),
        ("profile", "users"), ("capabilit", "users"), ("role", "users"),
        ("ms-", "sites/blogs"), ("network", "sites/blogs"), ("site", "sites/blogs"),
        ("meta", "meta"), ("option", "options"), ("bookmark", "links"),
        ("link-manager", "links"), ("link-add", "links"), ("link.php", "links"),
        ("post", "posts"), ("page", "posts"), ("attachment", "posts"),
        ("revision", "posts"), ("autosave", "posts"), ("media", "posts"),
        ("font-", "posts"), ("global-styles", "posts"),
    ):
        if marker in stem:
            return entity
    if stem == "link":
        return "links"
    return None


@dataclass(frozen=True)
class Token:
    tag: str
    value: str
    line: int


class Audit:
    def __init__(self, path, file, records):
        self.file = file
        self.lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        self.tokens = [Token(*record) for record in records]
        self.values = [token.value for token in self.tokens]
        self.end = {}
        self.parent = {}
        self.scope = {}
        self.params = {}
        self.assignments = defaultdict(list)
        self.by_position = {}
        self.domain = domain_from_context(file)
        self.is_rest = any(part in {"rest-api", "endpoints"} for part in file.parts)
        self.index_structure()
        self.index_assignments()

    def value(self, index):
        return self.values[index] if 0 <= index < len(self.values) else ""

    def index_structure(self):
        stack = []
        matching = {")": "(", "]": "[", "}": "{"}
        for index, token in enumerate(self.tokens):
            value = token.value
            self.parent[index] = stack[-1] if stack else None
            if value in ("(", "[", "{") or token.tag == "T_ATTRIBUTE":
                stack.append(index)
            if value in matching and stack:
                start = stack.pop()
                if self.value(start) in (matching[value], "#["):
                    self.end[start] = index
                    self.end[index] = start

        bodies = {}
        owners = []
        for index, token in enumerate(self.tokens):
            while owners and owners[-1][0] < index:
                owners.pop()
            class_name = next((name for _, kind, name in reversed(owners) if kind == "class"), "")
            function = next((name for _, kind, name in reversed(owners) if kind == "function"), "<file>")
            self.scope[index] = function
            if token.tag in ("T_CLASS", "T_TRAIT", "T_INTERFACE", "T_ENUM") and self.value(index - 1) != "::":
                pos = index + 1
                while self.value(pos) not in ("{", ";", ""):
                    pos = self.end.get(pos, pos) + 1
                if self.value(pos) == "{" and pos in self.end:
                    name = self.value(index + 1) if self.tokens[index + 1].tag == "T_STRING" else "<anonymous class>"
                    bodies[pos] = ("class", name)
            if token.tag in ("T_FUNCTION", "T_FN"):
                pos = index + 1
                if self.value(pos) == "&":
                    pos += 1
                name = self.value(pos) if self.value(pos + 1) == "(" else ""
                if name:
                    pos += 1
                if self.value(pos) == "(" and pos in self.end:
                    label = (class_name + "::" if class_name else "") + name if name else function + "::{closure}"
                    stop = self.end[pos] + 1
                    while self.value(stop) not in ("{", ";", "=>", ""):
                        stop = self.end.get(stop, stop) + 1
                    self.params[index] = (name, label, pos, stop)
                    if self.value(stop) == "{" and stop in self.end:
                        bodies[stop] = ("function", label)
                    for at in range(index, stop):
                        self.scope[at] = label
            if index in bodies:
                kind, name = bodies[index]
                owners.append((self.end[index], kind, name))

        # Scope for signature tokens would otherwise be overwritten by the loop.
        for start, (_, label, _, stop) in self.params.items():
            for index in range(start, stop):
                self.scope[index] = label

    def index_assignments(self):
        for index, token in enumerate(self.tokens):
            if token.tag == "T_VARIABLE" and self.value(index + 1) == "=":
                end = self.expression_end(index + 2)
                self.assignments[(self.scope[index], token.value)].append((index, index + 2, end))

    def expression_end(self, start):
        index = start
        while self.value(index) and self.value(index) not in (";", ",", ")", "]", "}", "=>", "&&", "||"):
            index = self.end.get(index, index) + 1 if self.value(index) in ("(", "[", "{") else index + 1
        return index

    def atom_end(self, index):
        """One operand with its call, array offsets and member accesses."""
        index = self.end.get(index, index) + 1 if self.value(index) in ("(", "[") else index + 1
        while True:
            if self.value(index) in ("[", "(") and index in self.end:
                index = self.end[index] + 1
            elif self.value(index) in ("->", "::", "?->"):
                index += 2
            else:
                return index

    def atom_start(self, index):
        if self.value(index) in ("]", ")") and index in self.end:
            opener = self.end[index]
            if self.value(index) == "]" or NAME_TOKEN.fullmatch(self.value(opener - 1)):
                index = self.atom_start(opener - 1)
            else:
                index = opener
        while self.value(index - 1) in ("->", "?->", "::"):
            index = self.atom_start(index - 2)
        return index

    def arguments(self, opener):
        if opener not in self.end:
            return []
        start = index = opener + 1
        end = self.end[opener]
        args = []
        while index < end:
            value = self.value(index)
            if value == ",":
                if start < index:
                    args.append((start, index))
                start = index + 1
            index = self.end.get(index, index) + 1 if value in ("(", "[", "{", "#[") else index + 1
        if start < end:
            args.append((start, end))
        return args

    def array(self, start, end):
        if self.value(start) == "array":
            start += 1
        if self.value(start) in ("[", "(") and self.end.get(start) == end - 1:
            return start
        return None

    def literal(self, span):
        start, end = span
        return self.value(start) if end - start == 1 and quoted(self.value(start)) else ""

    def context(self, index):
        label = self.scope.get(index, "")
        # Endpoint helper functions can explicitly name a different domain.
        method = label.split("::")[-1]
        if method.startswith(("mw_", "blogger_", "wp_", "mt_")) and "xmlrpc" in self.file.name:
            method_domain = domain_from_context(Path(method))
            if method_domain:
                return method_domain
            if method.lower().endswith("post"):
                return "posts"
            if method.lower().endswith("comment"):
                return "comments"
        return self.domain

    def key_entity(self, key, index):
        key = bare(key)
        result = name_entity(key)
        if result not in (None, "ambiguous"):
            return result, "high"
        if key in {"author", "authors"} and self.is_rest:
            return "users", "medium"
        if key in {"category", "categories", "tags", "terms", "menus"} and self.is_rest:
            return "terms", "medium"
        if key in {"featured_media", "media_id", "menu_item_parent"} and self.is_rest:
            return "posts", "medium"
        if key in {"parent", "parent_exclude", "include", "exclude", "id", "ids",
                   "parent_id", "object_id", "insert_id"} and self.context(index):
            if key == "object_id" and self.context(index) in {"meta", "terms", "term_taxonomy"}:
                return UNKNOWN
            return self.context(index), "medium"
        if result == "ambiguous":
            return UNKNOWN
        return None

    def resolve(self, start):
        """Nearest preceding simple assignment in this recorded function."""
        name = self.value(start)
        return next(((left, right) for at, left, right in reversed(
            self.assignments.get((self.scope.get(start), name), ())) if at < start), None)

    def query_key(self, index, key):
        key = bare(key)
        if QUERY.get(key) is None:
            return None
        left = self.value(index - 1)
        base = self.value(index - 2)
        if left == "[" and base in {"$query_vars", "query_vars", "$query_var", "$q", "$qv", "$wp_query"}:
            return QUERY[key]
        if self.file.name == "class-wp-query.php" and (
                left == "case" or self.value(index + 1) == "=>" or
                self.scope[index].endswith(("::fill_query_vars", "::generate_cache_key")) or
                (left == "[" and base == "$args")):
            return QUERY[key]
        if left == "(" and base in {"get_query_var", "set_query_var"}:
            return QUERY[key]
        if left == "(" and base in {"get", "set"} and self.value(index - 4) == "$wp_query":
            return QUERY[key]
        if self.file.name == "class-wp.php":
            parent = self.parent.get(index)
            if parent is not None and self.value(parent - 3) in {"$public_query_vars", "$private_query_vars"}:
                return QUERY[key]
        if self.value(index + 1) == "=>":
            parent = self.parent.get(index)
            if self.value(parent - 1 if parent is not None else -1) == "array":
                parent -= 1
            if parent is not None and self.value(parent - 2) in {"WP_Query", "get_posts", "query_posts"}:
                return QUERY[key]
            if parent is not None and self.value(parent - 1) == "=" and self.value(parent - 2) in {
                "$query", "$query_args", "$query_vars", "$wp_query_args",
            }:
                return QUERY[key]
        return None

    def variable_entity(self, name, index):
        if self.file.name == "class-wp-query.php":
            aliases = {
                "cat": "terms", "cat_array": "terms", "cat_in": "terms",
                "cat_not_in": "terms", "author": "users", "authors": "users",
            }
            if bare(name) in aliases:
                return aliases[bare(name)], "high"
            if bare(name).endswith("_for_where") and bare(name)[:-10] in QUERY:
                return QUERY[bare(name)[:-10]], "high"
        return self.key_entity(name, index)

    def classify(self, start, end, depth=0):
        """Classify a bounded operand, based on explicit keys, producers and local aliases."""
        if start >= end:
            return UNKNOWN
        values = self.values[start:end]
        first = values[0]
        if first == "(" and self.end.get(start) == end - 1:
            return self.classify(start + 1, end - 1, depth)
        if "??" in values:
            operand_end = self.atom_end(start)
            if self.value(operand_end) == "??":
                return self.classify(start, operand_end, depth)
        if first in {"-", "+", "@", "(int)", "(integer)"}:
            return self.classify(start + 1, end, depth)
        if first.lower().lstrip("\\") in {"absint", "intval", "abs", "wp_parse_id_list",
                                             "empty", "isset", "array_values", "array_keys",
                                             "array_unique"} and self.value(start + 1) == "(":
            args = self.arguments(start + 1)
            if args:
                return self.classify(*args[0], depth)
        if len(values) > 1 and (values[-1] == "]" or values[-2] in {"->", "?->", "::"}):
            if values[-1] == "]":
                offset = self.end.get(end - 1, -2)
                if offset == end - 3:
                    member = self.value(offset + 1)
                    if self.query_key(offset + 1, member):
                        return self.query_key(offset + 1, member), "high"
                    if quoted(member):
                        if NUMERIC_NAME.search(bare(member)) or bare(member) in {"cpage", "karma"}:
                            return NUMERIC
                        result = self.key_entity(member, offset + 1)
                        if result is not None:
                            return result
            else:
                member = values[-1]
                owner = bare(values[-3]) if len(values) >= 3 else ""
                if member == "insert_id" and owner == "wpdb":
                    return UNKNOWN
                if member == "ID":
                    for prefix in ("post", "page", "attachment", "revision", "menu_item",
                                   "comment", "user", "author", "term", "site", "blog"):
                        if owner == prefix or owner.endswith("_" + prefix):
                            return PREFIXES[prefix], "high"
                    if owner == "menu":
                        return "terms", "medium"
                result = self.key_entity(member, end - 1)
                if result is not None:
                    return result
                if NUMERIC_NAME.search(member):
                    return NUMERIC
        # Recognize UUID-bearing get_*_id producer calls even in nested wrappers.
        if self.value(start + 1) == "(" and self.end.get(start + 1) == end - 1:
            if first in {"count", "strlen", "sizeof", "time", "strtotime", "mb_strlen",
                         "floor", "ceil", "round", "filesize", "microtime"}:
                return NUMERIC
            if re.match(r"^(?:get_|wp_get_)", first):
                result = self.key_entity(re.sub(r"^(?:wp_)?get_", "", first), start)
                if result is not None:
                    return result
            if first in {"get_option", "get_query_var"}:
                args = self.arguments(start + 1)
                if args:
                    key = self.literal(args[0])
                    if first == "get_query_var" and bare(key) in QUERY:
                        return QUERY[bare(key)], "high"
                    if NUMERIC_NAME.search(bare(key)) or bare(key) in {"cpage", "karma"}:
                        return NUMERIC
                    result = self.key_entity(key, start)
                    if result:
                        return result
        if len(values) == 1 and first.startswith("$"):
            result = self.variable_entity(first, start)
            if result is not None and result[0] != "ambiguous":
                return result
            if depth < 2 and (assignment := self.resolve(start)):
                inferred = self.classify(*assignment, depth + 1)
                if inferred[0] in ENTITIES:
                    return inferred[0], "medium"
                if inferred == NUMERIC and result is None:
                    return NUMERIC
            if result is not None:
                return result
            if NON_ENTITY_ID.search(bare(first)):
                return NUMERIC
            if NUMERIC_NAME.search(bare(first)) or bare(first) in {
                "perpage", "i", "j", "n", "max", "min", "limit", "num", "total", "errno",
            }:
                return NUMERIC
        if len(values) == 1 and re.fullmatch(r"\d+(?:\.\d+)?", first.strip("'\"")):
            return NUMERIC
        return UNKNOWN

    def identity_like(self, start, end, result):
        if result[0] in ENTITIES:
            return True
        if result == NUMERIC:
            return False
        return any(name_entity(value) is not None for value in self.values[start:end]
                   if value.startswith("$") or quoted(value) or value == "ID")

    def add(self, index, pattern, kind, result, line=None, label=None):
        entity, confidence = result
        identity = "identity" if entity in ENTITIES else entity
        entity = entity if entity in ENTITIES else ""
        line = line if line is not None else self.tokens[index].line
        function = label if label is not None else self.scope[index]
        key = (index, line, pattern, kind, entity)
        self.by_position[key] = (
            self.file.as_posix(), line, function, pattern, entity, kind, identity,
            confidence, self.lines[line - 1].strip(),
        )

    def sql_domain(self, value):
        matches = set(re.findall(r"\$wpdb->(\w+)", value))
        domains = {SQL_TABLES[table] for table in matches if table in SQL_TABLES}
        return next(iter(domains)) if len(domains) == 1 else None

    def sql_column(self, column, domain, index):
        column = bare(column)
        if column == "id":
            return (domain, "high") if domain and domain != "ambiguous" else UNKNOWN
        if column == "object_id" and domain == "ambiguous":
            return "posts", "medium"  # Core term_relationships; other objects can be registered.
        if column == "parent":
            if domain == "term_taxonomy":
                return "terms", "high"
            return (domain, "medium") if domain and domain != "ambiguous" else UNKNOWN
        result = self.key_entity(column, index)
        if result is not None:
            return result
        if NUMERIC_NAME.search(column) or column in {
            "autoload", "post_date", "spam", "deleted", "archived", "public", "mature",
        }:
            return NUMERIC
        return UNKNOWN

    def sql_expression(self, span, depth=0):
        start, end = span
        if end - start == 1 and self.tokens[start].tag in {"string", "T_CONSTANT_ENCAPSED_STRING"}:
            return [(start, self.value(start))]
        if end - start == 1 and depth < 2 and self.value(start).startswith("$"):
            origin = self.resolve(start)
            return self.sql_expression(origin, depth + 1) if origin else []
        fragments = [(at, self.value(at)) for at in range(start, end)
                     if self.tokens[at].tag in {"string", "T_CONSTANT_ENCAPSED_STRING"}]
        if any(SQL_START.search(value) for _, value in fragments):
            return fragments
        return []

    def prepare(self, index, args):
        if not args:
            return
        fragments = self.sql_expression(args[0])
        if not fragments:
            return
        sql = "\n".join(value for _, value in fragments)
        domain = self.sql_domain(sql)
        values = args[1:]
        if len(values) == 1:
            array = self.array(*values[0])
            if array is not None:
                values = self.arguments(array)
            elif self.value(values[0][0]).startswith("$") and values[0][1] - values[0][0] == 1:
                origin = self.resolve(values[0][0])
                if origin and (array := self.array(*origin)) is not None:
                    values = self.arguments(array)
        generic = 0
        for match in PRINTF_FORMAT.finditer(sql):
            position, code = match.groups()
            if code is None:
                continue
            slot = int(position) - 1 if position else generic
            generic += 1
            if code != "d":
                continue
            result = self.classify(*values[slot]) if 0 <= slot < len(values) else UNKNOWN
            column = re.search(
                r"([a-z_]\w*)`?\s*(?:<=>|>=|<=|<>|!=|=|>|<|\b(?:NOT\s+)?IN\s*\()\s*['\"]?$",
                sql[:match.start()], re.I,
            )
            if column:
                field = self.sql_column(column[1], domain, index)
                if field != UNKNOWN:
                    result = field
            self.add(index, f"wpdb prepare %d #{slot + 1}", "sql-format", result)

    def data_fields(self, span):
        array = self.array(*span)
        if array is None:
            origin = self.resolve(span[0]) if span[1] - span[0] == 1 else None
            span = origin or span
            array = self.array(*span)
        start, end = span
        if self.value(start) == "compact" and self.end.get(start + 1) == end - 1:
            return [(self.literal((item, stop)), item, stop)
                    for item, stop in self.arguments(start + 1)]
        if array is None:
            return []
        return [(self.literal((start, start + 1)), start + 2, end)
                if self.value(start + 1) == "=>" else ("", start, end)
                for start, end in self.arguments(array)]

    def wpdb_data(self, index, method, args):
        if len(args) < 2:
            return
        table = args[0]
        if table[1] - table[0] == 1:
            table = self.resolve(table[0]) or table
        domain = self.sql_domain("".join(self.values[slice(*table)]))
        parts = [(1, 3 if method == "update" else 2, "data")]
        if method == "update":
            parts.append((2, 4, "where"))
        if method == "delete":
            parts = [(1, 2, "where")]
        for fields_at, format_at, part in parts:
            if fields_at >= len(args):
                continue
            fields = self.data_fields(args[fields_at])
            formats = []
            if format_at < len(args):
                fmt = args[format_at]
                array = self.array(*fmt)
                if array is None and fmt[1] - fmt[0] == 1 and (origin := self.resolve(fmt[0])):
                    fmt = origin
                    array = self.array(*fmt)
                if array is not None:
                    formats = [self.literal(item) for item in self.arguments(array)]
                elif self.literal(fmt):
                    formats = [self.literal(fmt)]
                elif self.value(fmt[0]) not in {"null", "NULL", "array"}:
                    self.add(index, f"wpdb {method} dynamic {part} format", "sql-format", UNKNOWN)
                    continue
            if formats:
                first_format = formats[0]
                for offset in range(max(len(fields), len(formats))):
                    fmt = formats[offset] if offset < len(formats) else first_format
                    if bare(fmt) != "%d":
                        continue
                    result = UNKNOWN
                    if offset < len(fields):
                        column, start, end = fields[offset]
                        result = self.sql_column(column, domain, index)
                        if result == UNKNOWN:
                            result = self.classify(start, end)
                    self.add(index, f"wpdb {method} {part} %d #{offset + 1}", "sql-format", result)
            else:
                for column, start, end in fields:
                    if bare(column) in self.implicit_fields:
                        result = self.sql_column(column, domain, index)
                        if result == UNKNOWN:
                            result = self.classify(start, end)
                        self.add(index, f"wpdb {method} {part} implicit %d ({bare(column)})",
                                 "sql-format", result)

    def all_calls(self, index):
        name = self.value(index).lower().lstrip("\\")
        if self.value(index + 1) != "(" or self.value(index - 1) in {"function", "fn"}:
            return
        args = self.arguments(index + 1)
        if not args:
            return
        start, end = args[0]
        if name in {"absint", "intval", "abs", "wp_parse_id_list", "is_numeric",
                    "ctype_digit", "is_int", "is_integer", "is_long", "filter_var"}:
            if name == "filter_var" and (len(args) < 2 or self.value(args[1][0]) not in
                    {"FILTER_VALIDATE_INT", "FILTER_SANITIZE_NUMBER_INT"}):
                return
            result = self.classify(start, end)
            if result == UNKNOWN and (kind_context := self.assigned_context(index)):
                result = kind_context
            kind = "cast" if name in {"absint", "intval", "abs", "wp_parse_id_list"} else "validation"
            self.add(index, name + "()", kind, result)
        elif name in {"array_map", "array_filter", "array_walk"} and len(args) >= 2:
            callback = bare(self.literal(args[0] if name == "array_map" else args[1]))
            if callback in {"intval", "absint", "is_int", "is_numeric", "ctype_digit"}:
                operand = args[1] if name == "array_map" else args[0]
                self.add(index, f"{name}({callback})",
                         "cast" if callback in {"intval", "absint"} else "validation",
                         self.classify(*operand))
        elif name in {"empty", "isset", "is_null"}:
            result = self.classify(start, end)
            if self.identity_like(start, end, result):
                self.add(index, name + "(ID)", "sentinel", result)
        elif self.value(index - 1) in {"->", "?->"} and self.value(index - 2) == "$wpdb":
            if name == "prepare":
                self.prepare(index, args)
            if name in {"insert", "replace", "update", "delete"}:
                self.wpdb_data(index, name, args)
        elif name in {"sprintf", "printf", "vsprintf", "vprintf"}:
            fmt = self.literal(args[0])
            if fmt:
                for offset, match in enumerate(m for m in PRINTF_FORMAT.finditer(fmt) if m[2]):
                    if match[2] not in {"d", "u", "i"}:
                        continue
                    slot = int(match[1]) if match[1] else offset + 1
                    result = self.classify(*args[slot]) if slot < len(args) else UNKNOWN
                    self.add(index, f"{name}({match[0]}) #{slot}", "other", result)
        elif name == "mysqli_insert_id":
            self.add(index, "mysqli_insert_id()", "other", UNKNOWN)
        elif name == "get_option" and self.literal(args[0]):
            result = self.key_entity(self.literal(args[0]), index)
            if result and result[0] in ENTITIES:
                self.add(index, f"get_option({bare(self.literal(args[0]))}) ID value", "other", result)
        elif name.startswith("wp_cache_"):
            self.cache(index, name, args)
        elif name in {"sort", "rsort", "asort", "arsort", "ksort", "krsort", "array_search", "in_array"}:
            result = self.classify(start, end)
            if self.identity_like(start, end, result):
                if name in {"in_array", "array_search"}:
                    if len(args) < 3 or self.value(args[2][0]).lower() != "true":
                        self.add(index, name + "() non-strict ID match", "validation", result)
                else:
                    self.add(index, name + "() ID ordering", "other", result)
        elif name in {"preg_match", "preg_match_all"} and len(args) >= 2:
            pattern = self.literal(args[0])
            result = self.classify(*args[1])
            if (r"\d" in pattern or "[0-9]" in pattern or "[:digit:]" in pattern) and self.identity_like(*args[1], result):
                self.add(index, name + "() numeric ID pattern", "validation", result)
        elif name in {"array_column", "wp_list_pluck"} and len(args) >= 2:
            for arg in args[1:3]:
                key = self.literal(arg)
                result = self.key_entity(key, index) if key else None
                source = self.values[slice(*args[0])]
                if bare(key) == "id" and any(bare(value) in {"categories", "terms", "tags"} for value in source):
                    result = "terms", "medium"
                elif bare(key) == "id" and any(bare(value) in {"posts", "pages", "attachments"} for value in source):
                    result = "posts", "medium"
                if result is not None:
                    self.add(index, f"{name}({bare(key)}) ID column/key", "other", result)

    def assigned_context(self, index):
        if index >= 1 and self.tokens[index - 1].tag == "T_INT_CAST":
            index -= 1
        for _ in range(3):
            if self.value(index - 1) != "(" or self.value(index - 2) not in {"absint", "intval", "abs"}:
                break
            index -= 2
        if self.value(index - 1) in {"=", "=>"}:
            left = self.atom_start(index - 2)
            if self.value(index - 1) == "=>" and quoted(self.value(left)):
                return self.key_entity(self.value(left), left)
            if bare(self.value(left)) == "id" and self.scope[index] == "wp_insert_comment":
                return "comments", "high"
            return self.classify(left, index - 1)
        return None

    def cache(self, index, name, args):
        start, end = args[0]
        group_at = 2 if name in {"wp_cache_add", "wp_cache_set", "wp_cache_replace",
                                 "wp_cache_set_salted", "wp_cache_incr", "wp_cache_decr"} else 1
        group = bare(self.literal(args[group_at])) if group_at < len(args) else ""
        result = self.classify(start, end)
        group_entity = CACHE_GROUPS.get(group)
        key = "".join(self.values[start:end])
        # Multiple writes use the keys of the first map, rather than its values.
        # Embedded key fragments, group interpolation and numeric literal keys
        # are also reviewable.
        if group_entity and not (quoted(key) and "$" not in key and not bare(key).isdigit()):
            result = group_entity, "medium"
        elif result[0] not in ENTITIES:
            for at in range(start, end):
                for name_in_key in re.findall(r"\$([a-z_]\w*)", self.value(at), re.I):
                    candidate = self.key_entity(name_in_key, at)
                    if candidate and candidate[0] in ENTITIES:
                        result = candidate[0], "medium"
                        break
                if result[0] in ENTITIES:
                    break
        if group_at < len(args) and result[0] not in ENTITIES:
            for at in range(*args[group_at]):
                for name_in_group in re.findall(r"\$([a-z_]\w*)", self.value(at), re.I):
                    candidate = self.key_entity(name_in_group, at)
                    if candidate and candidate[0] in ENTITIES:
                        result = candidate[0], "medium"
                        break
        if result[0] in ENTITIES or self.identity_like(start, end, result):
            self.add(index, name + (f" [{group}]" if group else " [dynamic group]"),
                     "cache-key", result)

    def signature(self, index):
        name, label, opener, stop = self.params[index]
        getter = re.match(r"^(?:wp_)?get_(.+?_ids?)(?:_from_.*)?$", name, re.I)
        getter_result = (self.key_entity(getter[1], index) or UNKNOWN) if getter else None
        if getter_result is not None:
            self.add(index, "get_*_id() declaration", "other", getter_result, label=label)
        for start, end in self.arguments(opener):
            for at in range(start, end):
                if self.tokens[at].tag == "T_VARIABLE":
                    types = self.values[start:at]
                    if "int" in types or "integer" in types:
                        result = self.classify(at, at + 1)
                        self.add(at, "int parameter", "type-decl", result, label=label)
                    break
        colon = self.end[opener] + 1
        if self.value(colon) == ":":
            for at in range(colon + 1, stop):
                if self.value(at).lower() != "int":
                    continue
                result = getter_result
                if result is None and re.search(r"(?:_id|_ids)$", name):
                    result = self.key_entity(name, index)
                if result is None and self.value(stop) == "{" and stop in self.end:
                    returns = {self.classify(ret + 1, self.expression_end(ret + 1))[0]
                               for ret in range(stop + 1, self.end[stop])
                               if self.value(ret) == "return" and self.scope.get(ret) == label}
                    identities = returns.intersection(ENTITIES)
                    if len(identities) == 1:
                        result = next(iter(identities)), "medium"
                self.add(at, "int return", "type-decl", result or UNKNOWN, label=label)

    def rest_schema(self, index):
        parent = self.parent.get(index)
        list_items = False
        while parent is not None:
            if self.value(parent) not in ("[", "("):
                break
            start = parent - 1 if self.value(parent - 1) == "array" else parent
            if self.value(start - 1) != "=>" or not quoted(self.value(start - 2)):
                break
            field = bare(self.value(start - 2))
            if field == "items":
                list_items = True
                parent = self.parent.get(parent)
                continue
            result = self.key_entity(field, index)
            if result is None:
                result = NUMERIC if NUMERIC_NAME.search(field) else UNKNOWN
            self.add(index, f"REST integer schema ({field}{'[]' if list_items else ''})",
                     "type-decl", result)
            break

    def string_hits(self, index, value):
        if SQL_START.search(value) or (
                re.search(r"\b(?:WHERE|AND|OR|SET|ON)\s+`?[a-z_]\w*`?\s*(?:=|<|>)", value, re.I)):
            domain = self.sql_domain(value)
            for match in re.finditer(
                r"\b([a-z_]\w*)`?\s*(=|<>|!=|<=|>=|<|>)\s*(['\"]?)0\3(?![.\w])", value, re.I,
            ):
                result = self.sql_column(match[1], domain, index)
                if result[0] in ENTITIES or result == UNKNOWN:
                    line = self.tokens[index].line + value.count("\n", 0, match.start())
                    self.add(index, f"SQL zero ({match[1]} {match[2]} 0)", "sentinel", result, line)
            for match in re.finditer(
                r"\b([a-z_]\w*)`?\s*(=|<>|!=|<=|>=|<|>)\s*(['\"]?)([1-9]\d*)\3(?![.\w])", value, re.I,
            ):
                result = self.sql_column(match[1], domain, index)
                if result[0] in ENTITIES:
                    line = self.tokens[index].line + value.count("\n", 0, match.start())
                    self.add(index, f"SQL numeric ID ({match[1]} {match[2]} {match[4]})",
                             "validation", result, line)
            for match in re.finditer(
                r"\b([a-z_]\w*)`?\s+[a-z]+(?:\s*\(\d+\))?\s+[^\n,]*?\bDEFAULT\s+['\"]?0['\"]?(?![.\w])",
                value, re.I,
            ):
                result = self.sql_column(match[1], domain, index)
                if result[0] in ENTITIES:
                    line = self.tokens[index].line + value.count("\n", 0, match.start())
                    self.add(index, f"SQL zero default ({match[1]})", "sentinel", result, line)
        if self.is_rest:
            for match in re.finditer(r"\(\?P<(\w+)>\s*(?:\(\?:)?\[?(?:\\+/)*(?:\\+d|0-9)", value):
                if re.match(r"0-9[a-zA-Z_]", value[match.end() - 3:]):
                    continue
                result = self.key_entity(match[1], index) or UNKNOWN
                self.add(index, f"REST numeric route ({match[1]})", "validation", result)
        if INT_FORMAT.search(value) and self.file.name == "load.php" and self.scope[index] == "wp_set_wpdb_vars":
            if self.value(index - 1) == "=>":
                column = self.value(index - 2)
                result = self.sql_column(column, None, index)
                self.add(index, f"wpdb field_types %d ({bare(column)})", "sql-format", result)

    def compare(self, index):
        left = self.atom_start(index - 1)
        if self.value(left).isdigit() and self.value(left - 1) in {"+", "-"} and self.value(left - 2) in {
                "(", "[", "=", ",", "=>", "return", "?", ":", "&&", "||", ""}:
            left -= 1
        right = self.atom_end(index + 1)
        if self.value(index + 1) in {"+", "-"}:
            right = self.atom_end(index + 2)
        first = self.classify(left, index)
        second = self.classify(index + 1, right)
        left_operand = "".join(self.values[left:index]).strip("'\"").lower()
        right_operand = "".join(self.values[index + 1:right]).strip("'\"").lower()
        operator = self.value(index)
        for result, span, other in (
                (first, (left, index), right_operand),
                (second, (index + 1, right), left_operand)):
            if not self.identity_like(*span, result):
                continue
            if other in {"0", "-0", "-1", "false", "null"}:
                self.add(index, f"ID {operator} {other}", "sentinel", result)
            elif not other and (left_operand or right_operand) and (
                    self.value(index - 1) in {"''", '""'} or self.value(index + 1) in {"''", '""'}):
                self.add(index, f"ID {operator} empty string", "sentinel", result)
            elif re.fullmatch(r"[+-]?\d+", other):
                self.add(index, f"ID {operator} {other}", "validation", result)
            elif operator in {"==", "!=", "<>", "<", ">", "<=", ">=", "<=>"} and (
                    first[0] in ENTITIES or second[0] in ENTITIES):
                self.add(index, f"ID {operator} expression", "validation", result)

    def scan(self, implicit_fields):
        self.implicit_fields = implicit_fields
        for index, token in enumerate(self.tokens):
            value = token.value
            after = self.value(index + 1)
            before = self.value(index - 1)
            if index in self.params:
                self.signature(index)
            if token.tag in {"T_STRING", "T_EMPTY", "T_ISSET", "T_NAME_FULLY_QUALIFIED"}:
                self.all_calls(index)
            if token.tag == "T_INT_CAST":
                end = self.atom_end(index + 1)
                result = self.classify(index + 1, end)
                if result == UNKNOWN:
                    result = self.assigned_context(index) or result
                self.add(index, re.sub(r"\s+", "", value).lower(), "cast", result)
            if token.tag in {"T_CONSTANT_ENCAPSED_STRING", "string"}:
                self.string_hits(index, value)
                if quoted(value):
                    if entity := self.query_key(index, value):
                        self.add(index, f"WP_Query {bare(value)}", "query-var", (entity, "high"))
                    if self.is_rest and bare(value) == "type" and after == "=>" and bare(self.value(index + 2)) == "integer":
                        self.rest_schema(index)
            if value in COMPARISONS:
                self.compare(index)
            if value == "!" and after not in {"empty", "isset", "is_numeric", "is_int", "ctype_digit"}:
                end = self.atom_end(index + 1)
                result = self.classify(index + 1, end)
                if self.identity_like(index + 1, end, result):
                    self.add(index, "! ID", "sentinel", result)
            if token.tag in {"T_IF", "T_ELSEIF", "T_WHILE"} and after == "(":
                start = index + 2
                end = self.atom_end(start)
                if self.value(start) not in {"empty", "isset", "is_null"} and self.value(end) in {")", "&&", "||", "and", "or"}:
                    result = self.classify(start, end)
                    if result[0] in ENTITIES:
                        self.add(start, "condition ID truthiness", "sentinel", result)
            if value in {"=", "=>", "??", "?:"} and self.value(index + 1).strip("'\"").lower() in {
                    "0", "null", "false"} and self.value(index + 2) in {",", ";", ")", "]", "}", ":", ""}:
                start = self.atom_start(index - 1)
                result = (self.key_entity(before, index - 1) or UNKNOWN) if value == "=>" else self.classify(start, index)
                if self.identity_like(start, index, result):
                    self.add(index, f"ID {value} {bare(after)}", "sentinel", result)
            if value == "return" and after in {"0", "false", "null"} and self.value(index + 2) == ";":
                function = self.scope[index].split("::")[-1]
                match = re.fullmatch(r"(?:wp_)?get_(\w+_ids?)", function)
                result = self.key_entity(match[1], index) if match else None
                if result and result[0] in ENTITIES:
                    self.add(index, f"ID return {after}", "sentinel", result)
            if token.tag == "T_VARIABLE" and before == "return" and after == "?":
                result = self.classify(index, index + 1)
                if result[0] in ENTITIES:
                    self.add(index, "return ID truthiness", "sentinel", result)
            if value == "insert_id" and before == "->":
                result = None if self.file.name == "class-wpdb.php" else self.assigned_context(index - 2)
                if (result is None or result == UNKNOWN) and self.scope[index] in {
                        "wp_insert_comment", "add_metadata", "trackback", "update_usermeta"}:
                    result = {
                        "wp_insert_comment": ("comments", "high"), "add_metadata": ("meta", "high"),
                        "trackback": ("comments", "medium"), "update_usermeta": ("meta", "high"),
                    }[self.scope[index]]
                self.add(index, "wpdb insert_id access", "other", result or UNKNOWN)
            if value == "$insert_id" and self.file.name == "class-wpdb.php" and before == "public":
                self.add(index, "wpdb insert_id property", "other", UNKNOWN)
            if value in {"-", "+", "++", "--", "-=", "+="} and not quoted(before):
                start, end = (index + 1, self.atom_end(index + 1)) if before in {
                    "(", "[", "=", ",", "=>", "return", "?"} else (self.atom_start(index - 1), index)
                result = self.classify(start, end)
                if result[0] in ENTITIES and (end == index + 1 or value in {"++", "--", "-=", "+="}
                                             or self.value(index + 1).isdigit() or start == index + 1):
                    self.add(index, f"ID arithmetic {value}", "other", result)


def audit(root, rows):
    paths = source_files(root)
    load = (root / "src/wp-includes/load.php").read_text(encoding="utf-8")
    mapping = re.search(r"\$wpdb->field_types\s*=\s*array\s*\((.*?)\);", load, re.S)
    implicit = {field.lower() for field in re.findall(r"['\"](\w+)['\"]\s*=>\s*['\"]%d['\"]", mapping[1])}
    excluded = included = 0
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as manifest:
        manifest.writelines(f"{path}\n" for path in paths)
        manifest.seek(0)
        with subprocess.Popen(["php", str(Path(__file__).with_name("tokens.php"))],
                              stdin=manifest, stdout=subprocess.PIPE, text=True, encoding="utf-8") as lexer:
            for path in paths:
                record = lexer.stdout.readline()
                if not record:
                    raise RuntimeError(f"PHP lexer stopped before {path}")
                file = path.relative_to(root)
                analysis = Audit(path, file, json.loads(record))
                analysis.scan(implicit)
                hits = list(analysis.by_position.values())
                if any(part.lower() in EXCLUDED for part in file.parts):
                    excluded += 1
                    # Keep explicit database-backed WP entity uses inside vendored code.
                    hits = [hit for hit in hits if hit[6:8] == ("identity", "high")
                            and re.search(r"\$(?:wpdb|post|comment|user|term)->|\bwp_parse_id_list\(", hit[8])]
                else:
                    included += 1
                rows.extend(hits)
            if lexer.wait() != 0:
                raise RuntimeError("PHP tokenizer exited with an error")
    print(f"Lexed {len(paths)} PHP files: {included} core paths and {excluded} bundled paths screened for explicit WP entities.",
          file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="WordPress develop checkout root")
    parser.add_argument("output", type=Path, help="CSV output path")
    args = parser.parse_args()
    if not (args.reference / "src/wp-includes/version.php").is_file():
        parser.error("reference must point to a WordPress develop checkout")
    rows = []
    audit(args.reference.resolve(), rows)
    rows.sort(key=lambda row: (row[0], row[1], row[3], row[4], row[2]))
    with args.output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
