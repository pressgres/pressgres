#!/usr/bin/env python3
"""Inventory ID assumptions in the pinned WordPress and Gutenberg source trees."""
import argparse
import bisect
import csv
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
WP = 'wordpress-develop-7.1.5'
GB = 'gutenberg-89408c2'
REST = 'src/wp-includes/rest-api'
ENDPOINTS = REST + '/endpoints/class-wp-rest-'
PHP_TOKEN = re.compile(
    r"""//[^\n]*|/\*[\s\S]*?\*/|\#[^\[\n][^\n]*|'(?:\\.|[^'\\])*'|"""
    r'''"(?:\\.|[^"\\])*"|\$?\w+|=>|->|::|[^\s]'''
)
CAPTURE = re.compile(r'\(\?P<(\w+)>((?:(?:\(\?:[^)]*\))|[^)])+)\)')
BASES = {
    'posts': '{post-base}', 'revisions': '{post-base}/{parent}/revisions',
    'autosaves': '{post-base}/{parent}/autosaves', 'attachments': 'media',
    'terms': '{taxonomy-base}', 'menus': 'menus', 'menu-items': 'menu-items',
    'global-styles-revisions': 'global-styles/{parent}/revisions',
    'templates': '{template-base}', 'template-revisions': '{template-base}/{template}/revisions',
    'template-autosaves': '{template-base}/{template}/autosaves',
    'font-faces': 'font-families/{font_family_id}/font-faces',
    'application-passwords': 'users/{user_id}/application-passwords',
    'block-renderer': 'block-renderer/{name}', 'pattern-directory': 'pattern-directory/patterns',
}

ENTITIES = {
    'author': 'user', 'author_exclude': 'user', 'selectedauthor': 'user',
    'reassign': 'user', 'user_id': 'user', 'userid': 'user', 'featured_media': 'attachment',
    'featuredmedia': 'attachment', 'site_icon': 'attachment', 'site_logo': 'attachment',
    'mediaid': 'attachment', 'attachmentid': 'attachment', 'imageid': 'attachment',
    'post': 'post', 'post_id': 'post', 'postid': 'post', 'page_on_front': 'page',
    'page_for_posts': 'page', 'parentpageid': 'page', 'wp_id': 'template backing post',
    'categories': 'category term', 'tags': 'tag term', '$tax_base': 'taxonomy term',
    'terms': 'taxonomy term', 'termid': 'taxonomy term', 'menu': 'menu term',
    'PROP_ID': 'post or term (by search type)', 'font_faces': 'font face post',
    'menus': 'menu term', 'font_family_id': 'font family post', 'commentid': 'comment',
    'object_id': 'post or term (by menu item type)', 'ref': 'referenced post',
}

REST_FIELDS = ['route', 'source', 'kind', 'property', 'entity', 'current_type',
               'required_change', 'severity', 'confidence', 'evidence']
JS_FIELDS = ['source', 'symbol', 'entity', 'kind', 'severity', 'confidence',
             'current_type', 'persistence', 'required_change', 'evidence']


class Source:
    def __init__(self, root, path):
        self.path = path.relative_to(root).as_posix()
        self.prefix = root.name
        self.text = path.read_text(encoding='utf-8')
        self.lines = self.text.splitlines()
        self.starts = [0] + [m.end() for m in re.finditer('\n', self.text)]

    def line(self, offset):
        return bisect.bisect_right(self.starts, offset)

    def location(self, line):
        return f'{self.prefix}/{self.path}:{line}'


def compact(value):
    return ' '.join(value.split())


def php_tokens(source):
    return [(m.group(), source.line(m.start()), m.start()) for m in PHP_TOKEN.finditer(source.text)
            if not m.group().startswith(('//', '/*', '#'))]


def unquote(token):
    return token[1:-1] if token.startswith(("'", '"')) else token


def controller(source):
    filename = Path(source.path).stem
    return re.sub(r'(?:^class-wp-rest-|-controller$)', '', filename)


def default_route(name):
    if name == 'navigation-fallback':
        return '/wp-block-editor/v1/navigation-fallback'
    return '/wp/v2/' + BASES.get(name, name)


def route_expression(tokens, name):
    """Resolve the pinned registration forms into route templates."""
    values = [token[0] for token in tokens]
    if values[0] == 'sprintf' and name in ('template-autosaves', 'template-revisions'):
        revision = next((unquote(value) for value in values if '(?P<id>[\\d]' in value), '')
        base = '/{template-base}/{template}/' + name.split('-')[-1]
        return base + ('/' + revision if revision else '')
    if values[0] != "'/'" and not values[0].startswith("'"):
        return '/{' + name + '-route}'
    base = BASES.get(name, name)
    if name in ('revisions', 'autosaves', 'global-styles-revisions'):
        parent, leaf = base.split('/{parent}/')
    else:
        parent, leaf = '{parent-base}', base
    leaf = {
        'application-passwords': r'users/(?P<user_id>(?:[\d]+|me))/application-passwords',
        'font-faces': r'font-families/(?P<font_family_id>[\d]+)/font-faces',
        'block-renderer': 'block-renderer',
        'pattern-directory': 'pattern-directory',
    }.get(name, leaf)
    expression = ''.join(unquote(value) for value in values if value not in ('.',))
    return expression.replace('$this->rest_base', leaf).replace('$this->parent_base', parent)


def property_entity(name, key):
    if key in ENTITIES:
        return ENTITIES[key]
    default = {
        'users': 'user', 'comments': 'comment', 'terms': 'taxonomy term', 'menus': 'menu term',
        'attachments': 'attachment', 'font-families': 'font family post', 'font-faces': 'font face post',
        'application-passwords': 'user', 'global-styles': 'global styles post',
        'global-styles-revisions': 'global styles revision post', 'revisions': 'revision post',
        'autosaves': 'autosave revision post', 'template-revisions': 'template revision post',
        'template-autosaves': 'template autosave revision post', 'navigation-fallback': 'navigation post',
        'menu-items': 'menu item post', 'pattern-directory': 'upstream pattern directory record',
        'search': 'post or term (by search type)',
    }.get(name, 'post')
    if key == 'parent':
        return {'font-faces': 'font family post', 'revisions': 'post', 'autosaves': 'post',
                'global-styles-revisions': 'global styles post', 'template-revisions': 'template backing post',
                'template-autosaves': 'template backing post'}.get(name, default)
    return default


def rest_row(source, line, kind, key, current, change, *, route=None, entity=None,
             severity='breaks-with-uuid', confidence='high', evidence=None):
    name = controller(source)
    return dict(route=route or default_route(name), source=source.location(line), kind=kind,
                property=key, entity=entity or property_entity(name, key), current_type=current,
                required_change=change, severity=severity, confidence=confidence,
                evidence=evidence or source.lines[line - 1].strip())


def rest_routes(source, tokens):
    name = controller(source)
    rows, spans = [], []
    for i, (value, line, _) in enumerate(tokens[:-1]):
        if value != 'register_rest_route' or tokens[i + 1][0] != '(':
            continue
        if i and tokens[i - 1][0] == 'function':
            continue
        args = [[]]
        depth = 0
        for token in tokens[i + 2:]:
            text = token[0]
            if depth == 0 and text == ')':
                break
            if depth == 0 and text == ',':
                args.append([])
                continue
            depth += (text in ('(', '[', '{')) - (text in (')', ']', '}'))
            args[-1].append(token)
        if len(args) < 2 or not args[1]:
            continue
        pattern = route_expression(args[1], name)
        namespace = unquote(args[0][0][0]) if len(args[0]) == 1 else 'wp/v2'
        if namespace.startswith('$'):
            ns = re.search(r"\$this->namespace\s*=\s*'([^']+)'", source.text)
            namespace = ns[1] if ns else 'wp/v2'
        route = '/' + namespace + pattern
        captures = list(CAPTURE.finditer(pattern))
        for capture in reversed(captures):
            start, end = capture.span()
            key = capture[1]
            if name == 'autosaves' and key == 'id' and pattern.endswith('/autosaves'):
                key = 'parent'
            route = route[:start + len(namespace) + 1] + '{' + key + '}' + route[end + len(namespace) + 1:]
        if len(args) > 2 and args[2]:
            spans.append((args[2][0][1], args[2][-1][1], route))
        for capture in captures:
            key, pattern_text = capture.groups()
            if not re.fullmatch(r'(?:\(\?:)?\[?[\\/d0-9+\-]+\]?\+?(?:\|me\))?', pattern_text):
                continue
            # Require a decimal digit expression, not merely a digit in a slug class.
            if r'\d' not in pattern_text and '0-9' not in pattern_text:
                continue
            evidence_token = next((token for token in args[1] if capture[0] in token[0]), None)
            spot = evidence_token[1] if evidence_token else args[1][0][1]
            origin = {
                ('application-passwords', 'user_id'): source.location(26),
                ('font-faces', 'font_family_id'): f'{WP}/src/wp-includes/post.php:654',
            }.get((name, key))
            entity = 'post' if name == 'autosaves' and route.endswith('/autosaves') else None
            if name == 'template-autosaves' or name == 'template-revisions':
                spot = next(token[1] for token in args[1] if '(?P<id>' in token[0])
            rows.append(rest_row(source, spot, 'route', key, capture[0],
                                 'Match and validate canonical UUIDv7' +
                                 (' while preserving the me alias' if '|me' in pattern_text else ''),
                                 route=route, entity=entity,
                                 evidence=capture[0] + (f' defined at {origin}' if origin else '')))
    return rows, spans


def array_properties(tokens):
    """Yield the key ancestry for literal PHP array entries."""
    stack = []
    def indexes(index):
        keys = []
        while index > 1 and tokens[index][0] == ']' and tokens[index - 2][0] == '[':
            keys.insert(0, unquote(tokens[index - 1][0]))
            index -= 3
        return keys

    for i, (value, line, _) in enumerate(tokens):
        previous = tokens[i - 1][0] if i else ''
        before = tokens[i - 2][0] if i > 1 else ''
        if value in ('(', '[', '{'):
            keys = []
            if previous == 'array' and before == '=>':
                keys = [unquote(tokens[i - 3][0])]
            elif previous == 'array' and before == '=':
                keys = indexes(i - 3)
            elif value == '[' and previous == '=>':
                keys = [unquote(before)]
            stack.append((value, keys))
        elif value in (')', ']', '}'):
            opening = {')': '(', ']': '[', '}': '{'}[value]
            if stack and stack[-1][0] == opening:
                stack.pop()
        elif i + 2 < len(tokens) and tokens[i + 1][0] == '=>':
            keys = [key for _, group in stack for key in group]
            if unquote(value) == 'type' and tokens[i + 2][0] == 'array':
                end = next(j for j in range(i + 4, len(tokens)) if tokens[j][0] == ')')
                types = [unquote(t[0]) for t in tokens[i + 4:end] if t[0] != ',']
                if 'integer' in types:
                    yield keys, unquote(value), '|'.join(types), line
            else:
                yield keys, unquote(value), unquote(tokens[i + 2][0]), line
        elif value == '=':
            keys = indexes(i - 1)
            if keys and keys[-1] in ('type', 'sanitize_callback'):
                yield keys[:-1], keys[-1], unquote(tokens[i + 1][0]), line


UNRELATED_INTEGER = {
    'page', 'per_page', 'offset', 'count', 'order', 'menu_order', 'block_version',
    'version', 'perPage', 'rating_count', 'active_installs', 'author_block_count',
    'api_version', 'width', 'height', 'filesize', 'rotation', 'viewport_width',
    'theme_json_version', 'length', 'time', 'timestamp', 'posts_per_page',
}


def rest_schema(source, tokens, spans, debug):
    name = controller(source)
    rows = []
    for parents, field, value, line in array_properties(tokens):
        if not parents:
            continue
        key = parents[-1]
        if ((field == 'type' and 'integer' in value.split('|')) or
                (field == 'sanitize_callback' and value in ('absint', 'wp_parse_id_list'))):
            if debug:
                print(f'{name}:{line}: {".".join(parents)} {field}={value}')
            leaf = next((k for k in reversed(parents) if k != 'items'), key)
            if leaf in UNRELATED_INTEGER:
                continue
            if (leaf not in ENTITIES and leaf not in {
                'id', 'parent', 'parent_exclude', 'include', 'exclude', 'post__in', 'post__not_in',
                'default_category', 'default_link_category', 'menu_id', 'object', 'parents',
                '$base', '$rest_base', 'font_faces', '$rest_key', 'PROP_ID',
            } and not (name == 'posts' and parents == ['oneOf', 'items'])):
                continue
            route = next((route for start, end, route in spans if start <= line <= end), None)
            remote = name == 'pattern-directory'
            entity = property_entity(name, 'parent' if leaf in ('parent_exclude', 'parents') else leaf)
            if name == 'menu-items' and leaf == 'object':
                entity = 'post or term (by menu item type)'
            if leaf in ('$base', '$rest_base', '$rest_key') or parents == ['oneOf', 'items']:
                entity = 'taxonomy term' if not (name == 'menu-items' and leaf == '$base') else 'menu term'
            rows.append(rest_row(
                source, line, 'schema' if field == 'type' else 'sanitize', '.'.join(parents), value,
                'Preserve upstream external ID' if remote else
                'Use a UUID-aware sanitizer and preserve field-specific missing semantics'
                if field != 'type' else
                'Require UUIDv7 for local search results and retain nonentity string keys'
                if leaf == 'PROP_ID' else 'Declare and validate canonical UUIDv7 string' +
                (' items' if 'items' in parents else '') + ' with field-specific missing semantics',
                route=route, entity=entity, severity='cosmetic' if remote else 'breaks-with-uuid',
            ))
    return rows


def rest_inventory(root, debug):
    rows = []
    sources = sorted((root / 'src').rglob('*.php'))
    for path in sources:
        source = Source(root, path)
        in_rest = source.path.startswith(REST + '/') or source.path == REST + '.php'
        if not in_rest and not re.search(r'\bregister_rest_route\s*\(', source.text):
            continue
        tokens = php_tokens(source)
        routes, spans = rest_routes(source, tokens)
        rows.extend(routes)
        rows.extend(rest_schema(source, tokens, spans, debug))
    from rest_evidence import evidence_rows
    rows.extend(evidence_rows(root))
    return rows


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (
            row['source'].rsplit(':', 1)[0], int(row['source'].rsplit(':', 1)[1]),
            row['kind'], row.get('property', row.get('symbol')))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path, help='directory containing the two pinned trees')
    parser.add_argument('--output', type=Path, default=HERE.parents[2] / 'docs/research/data')
    parser.add_argument('--review-integers', action='store_true')
    args = parser.parse_args()
    for name in (WP, GB):
        if not (args.reference / name).is_dir():
            parser.error(f'missing {args.reference / name}')
    args.output.mkdir(parents=True, exist_ok=True)
    rest = rest_inventory(args.reference / WP, args.review_integers)
    write_csv(args.output / 'R-012-rest-hits.csv', REST_FIELDS, rest)
    print('REST', len(rest), dict(sorted(Counter(row['kind'] for row in rest).items())))
    from javascript import inventory
    js, sources = inventory(args.reference / GB)
    write_csv(args.output / 'R-012-js-hits.csv', JS_FIELDS, js)
    print('JS', len(js), dict(sorted(Counter(row['kind'] for row in js).items())),
          f'across {len(sources)} source files')


if __name__ == '__main__':
    main()
