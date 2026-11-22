"""Gutenberg source inventory and block metadata classification for R-012."""
import json
import re
from audit import Source, compact

EXCLUDED = {'test', 'tests', '__tests__', '__mocks__', '__fixtures__', 'fixtures',
            'story', 'stories', '__stories__', 'storybook', '__snapshots__', 'benchmarks'}
CODE = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}
# Each entry is an entity-bearing numeric schema confirmed against its consumer.
BLOCK_IDS = {
    ('audio', 'id'): 'attachment',
    ('avatar', 'userId'): 'user',
    ('block', 'ref'): 'synced pattern post',
    ('cover', 'id'): 'attachment',
    ('file', 'id'): 'attachment',
    ('gallery', 'ids.items'): 'attachment',
    ('image', 'id'): 'attachment',
    ('latest-posts', 'selectedAuthor'): 'user',
    ('media-text', 'mediaId'): 'attachment',
    ('navigation', 'ref'): 'navigation post',
    ('navigation-link', 'id'): 'post or taxonomy term (by kind/type)',
    ('navigation-submenu', 'id'): 'post or taxonomy term (by kind/type)',
    ('page-list', 'parentPageID'): 'page',
    ('page-list-item', 'id'): 'page',
    ('playlist-track', 'id'): 'attachment',
    ('post-comment', 'commentId'): 'comment',
    ('video', 'id'): 'attachment',
}
COMPOSITE = {
    ('gallery', 'images.query.id'): ('attachment', 'legacy markup (data-id)'),
    ('latest-posts', 'categories'): ('category term', 'comment JSON (array of objects with id)'),
    ('query', 'query'): ('user, post and taxonomy term', 'comment JSON (author, parents, exclude, taxQuery)'),
}
ID = (r'(?<![\w$])(?:[A-Za-z_$][\w$]*(?:\?\.|\.)\s*)*'
      r'(?:\b(?:id|ids|ref|author|parent|categories|tags|featured_media|wp_id)\b|'
      r'\b[A-Za-z_$][\w$]*(?:Id|Ids|ID|IDs|_id|_ids)\b)')
ID_RE = re.compile(ID)
COMPARE = r'(?:===|!==|==|!=|>=|<=|>|<)'
NUMBER = r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])'
CONVERT = re.compile(r'\b(?:Number(?:\.(?:parseInt|isInteger|isNaN|isFinite))?|parseInt|parseFloat|'
                     r'isNaN|isFinite|isNumericID)\s*\(\s*(' + ID + r')', re.M)
UNARY = re.compile(r'(?<![\w+])\+\s*(' + ID + r')(?=\s*[,);}\]])')
TYPES = re.compile(r'(' + ID + r')\s*\??\s*:\s*(?:(?:readonly\s+)?number\b|(?:Readonly)?Array\s*<\s*number\b)')
DOC_TYPE = re.compile(r'\{\s*(?:number|Number)(?:\[\])?\s*\}\s*\[?(' + ID + r')')
COMPARE_ID = re.compile(r'(' + ID + r')\s*' + COMPARE + r'\s*' + NUMBER + r'|' +
                        NUMBER + r'\s*' + COMPARE + r'\s*(' + ID + r')')
TYPEOF = re.compile(r'\btypeof\s+(' + ID + r')\s*' + COMPARE + r"""\s*['"]number['"]""")
FALSY = re.compile(r'(?<!!)!\s*(' + ID + r')(?!\s*(?:\.|\?\.|\[|\(|=))(?=\s*[),};?:&|])')
MATH = re.compile(r'(' + ID + r')\s*(?:[-+*/%]\s*' + NUMBER + r'|\+\+|--)(?![\w.])')
SORT = re.compile(r'(' + ID + r')\s*-\s*(' + ID + r')')
QUERY = re.compile(r'\baddQueryArgs\s*\(')
COMMENT = re.compile(r'^\s*(?://|/\*|\*|#)')
NOT_ENTITY = re.compile(r'(?:^|\.)(?:clientIds?|queryId|noticeId|instanceId|requestId|'
                        r'timeoutId|intervalId|clipPathId|panelId|anchorId|pointerId|'
                        r'draggedId|attachmentIndex|ruleId|fieldId|tabId|selectionId|'
                        r'labelId|controlId|inputId|descriptionId|headingId|uniqueId|glyphId|gridItemId)$', re.I)


def js_row(source, line, symbol, entity, kind, severity, confidence, current, change,
           persistence='', evidence=None):
    return dict(source=source.location(line), symbol=symbol, entity=entity, kind=kind,
                severity=severity, confidence=confidence, current_type=current,
                persistence=persistence, required_change=change,
                evidence=evidence or source.lines[line - 1].strip())


def attr_rows(source):
    metadata = json.loads(source.text)
    block = metadata['name'].split('/')[-1]
    rows = []

    def visit(attributes, prefix=''):
        for name, definition in attributes.items():
            key = prefix + name
            numeric = BLOCK_IDS.get((block, key))
            composite = COMPOSITE.get((block, key))
            if numeric or composite:
                name_lines = [i for i, text in enumerate(source.lines, 1)
                              if re.match(r'\s*"' + re.escape(name) + r'"\s*:', text)]
                if key == 'ids.items':
                    name_lines = [i for i in name_lines if i > next(
                        i for i, text in enumerate(source.lines, 1) if '"ids":' in text)]
                if numeric:
                    assert definition['type'] in ('integer', 'number') and not definition.get('source')
                    entity, persistence, severity = numeric, 'comment JSON', 'breaks-with-uuid'
                    change = 'Declare a string UUID and migrate by entity crosswalk'
                else:
                    entity, persistence = composite
                    severity = 'degrades' if key == 'images.query.id' else 'breaks-with-uuid'
                    change = 'Migrate and validate entity references inside this payload'
                if persistence == 'comment JSON' and metadata.get('__experimental'):
                    persistence += ' (experimental block)'
                if block == 'page-list-item' and key == 'id':
                    persistence += ' (generated preview child in normal Page List)'
                rows.append(js_row(source, name_lines[0], metadata['name'] + '.' + key, entity,
                                   'block-attr', severity, 'high', definition['type'], change, persistence))
            if 'items' in definition:
                visit({'items': definition['items']}, key + '.')
            if 'query' in definition:
                visit(definition['query'], key + '.query.')

    visit(metadata.get('attributes', {}))
    if 'postId' in metadata.get('usesContext', []):
        line = next(i for i, text in enumerate(source.lines, 1) if '"postId"' in text)
        rows.append(js_row(source, line, metadata['name'] + '.postId', 'post',
                           'schema', 'cosmetic', 'high', 'inherited context',
                           'Pass UUID strings through provider and consumer', 'runtime context'))
    return rows


def infer_entity(source, name):
    raw = re.sub(r'[^a-z]', '', name.split('.')[-1].lower())
    for entity, pattern in (
        ('attachment', r'^(attachment|media|image|featuredmedia|sitelogo|siteicon)'),
        ('user', r'^(user|author|selectedauthor|currentuser|reassign)'),
        ('taxonomy term', r'^(term|taxonomy|categor|tag)'),
        ('comment', r'^(comment|note)'),
        ('navigation or menu term', r'^(nav|menu)'),
        ('post', r'^(post|page|revision|template)'),
    ):
        if re.match(pattern, raw):
            return entity
    if raw == 'ref' and '/navigation/' in source.path:
        return 'navigation post'
    if '/media' in source.path or re.search(r'/(?:image|gallery|file|video|audio)/', source.path):
        return 'attachment (inferred)'
    return 'entity unresolved'


PATTERNS = (
    ('parse', CONVERT, 'numeric conversion or validation', 'Preserve and validate UUID strings'),
    ('parse', UNARY, 'unary numeric conversion', 'Remove numeric coercion and validate the UUID'),
    ('compare', COMPARE_ID, 'numeric comparison', 'Use explicit missing state and string equality'),
    ('compare', TYPEOF, 'number type gate', 'Validate by entity key contract'),
    ('arithmetic', MATH, 'numeric operation candidate', 'Use an explicit ordinal or a UUID-preserving operation'),
    ('sort', SORT, 'numeric subtraction candidate', 'Sort by the intended order field'),
    ('type', TYPES, 'number type candidate', 'Use entity UUID string types in source and generated declarations'),
    ('type', DOC_TYPE, 'number JSDoc', 'Document entity UUID string types'),
    ('compare', FALSY, 'falsy guard (sentinel candidate)', 'Check field-specific missing semantics'),
)


def js_candidates(source):
    for kind, pattern, current, change in PATTERNS:
        for match in pattern.finditer(source.text):
            symbol = next(group for group in match.groups() if group is not None)
            line = source.line(match.start())
            if NOT_ENTITY.search(symbol) or re.search(r'clientIds?$', symbol, re.I):
                continue
            if COMMENT.match(source.lines[line - 1]) and pattern != DOC_TYPE:
                continue
            if pattern == UNARY:
                preceding = source.text[:match.start()].rstrip()
                if not re.search(r'(?:^|[=(:,[!?;]|=>|[!=]==|\breturn)\s*$', preceding):
                    continue
            if pattern == SORT:
                scope = ' '.join(source.lines[max(0, line - 5):line])
                if not re.search(r'\bsort\b|compare|orderBy', scope, re.I):
                    continue
            severity = 'degrades' if pattern == FALSY or kind in ('type', 'sort') else 'breaks-with-uuid'
            yield js_row(source, line, symbol, infer_entity(source, symbol), kind, severity,
                         'medium' if pattern != FALSY else 'low', current, change,
                         evidence=compact(match.group()) + ' | ' + source.lines[line - 1].strip())
    for match in QUERY.finditer(source.text):
        line = source.line(match.start())
        if COMMENT.match(source.lines[line - 1]):
            continue
        end = balanced_call(source.text, match.end() - 1)
        expression = source.text[match.end():end]
        for key in dict.fromkeys(m.group() for m in ID_RE.finditer(expression)
                                 if not NOT_ENTITY.search(m.group()) and m.group() not in {'id', 'ref', 'parent'}):
            yield js_row(source, line, key, infer_entity(source, key), 'url', 'degrades',
                         'medium', 'query value (verify provenance)',
                         'Preserve canonical UUIDs and check the destination parameter',
                         evidence=compact(expression)[:500])


def balanced_call(text, opening):
    """Return the call's closing paren, skipping quoted literals."""
    tokens = re.compile(r"""'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`|[()]""")
    depth = 0
    for token in tokens.finditer(text, opening):
        depth += (token.group() == '(') - (token.group() == ')')
        if not depth:
            return token.start()
    return opening


def inventory(root):
    rows = []
    sources = {}
    for path in sorted((root / 'packages').glob('*/src/**/*')):
        relative = path.relative_to(root).parts
        if (not path.is_file() or len(relative) < 4 or 'react-native' in relative[1] or
                relative[1].startswith(('e2e-test-', 'test-')) or
                any(part in EXCLUDED or part == 'native' for part in relative[3:-1]) or
                re.search(r'\.(?:test|spec|story|stories|native|ios|android)\.', path.name)):
            continue
        if path.suffix not in CODE and path.name != 'block.json':
            continue
        source = Source(root, path)
        sources[source.path] = source
        rows.extend(attr_rows(source) if path.name == 'block.json' else js_candidates(source))
    from js_evidence import reviewed_rows
    reviewed = reviewed_rows(sources)
    reviewed_keys = {(row['source'], row['kind']) for row in reviewed}
    rows = [row for row in rows if (row['source'], row['kind']) not in reviewed_keys]
    rows.extend(reviewed)
    return rows, sources
