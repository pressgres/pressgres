"""Reviewed call chains and aliases that the lexical scan cannot identify."""
from javascript import js_row

# Source lines tie classifications to the pinned snapshot. A branch supporting
# numeric keys can coexist with a working UUID path, so those get cosmetic.
SITES = {
    'block-editor/src/store/private-selectors.js': [
        (601, 'patternName', 'synced pattern post', 'parse', 'parseInt on pattern slug suffix')],
    'block-library/src/image/transforms.js': [
        (139, 'wp-image-*', 'attachment', 'schema', 'digits-only class recognizer'),
        (187, 'wp-image-*', 'attachment', 'parse', 'digits-only class capture'),
        (190, 'idMatches', 'attachment', 'parse', 'Number on class capture')],
    'block-library/src/latest-posts/edit.js': [
        (510, 'selectedAuthor', 'user', 'parse', 'Number on author option value')],
    'block-library/src/post-comment/edit.js': [
        (39, 'commentId', 'comment', 'parse', 'parseInt on comment ID input')],
    'core-data/src/actions.js': [
        (331, 'recordId', 'template backing post', 'compare', 'numeric vs composite template route'),
        (665, 'recordId', 'template backing post', 'compare', 'numeric vs composite template route')],
    'core-data/src/entities.js': [
        (26, 'DEFAULT_ENTITY_KEY', 'configured entity', 'schema', 'id field name, independent of value type'),
        (414, 'revisionKey', 'template backing post', 'schema', 'wp_id or DEFAULT_ENTITY_KEY'),
        (447, 'objectId', 'post', 'parse', 'parseInt on CRDT document identity')],
    'core-data/src/queried-data/reducer.js': [
        (92, 'itemId', 'configured entity', 'parse', 'integer branch followed by UUID-safe strict string fallback'),
        (93, 'id', 'configured entity', 'parse', 'unary + only on numeric item removal branch')],
    'core-data/src/reducer.js': [
        (346, 'itemId', 'revision post', 'parse', 'integer branch followed by UUID-safe strict string fallback'),
        (347, 'id', 'revision post', 'parse', 'unary + only on numeric revision removal branch')],
    'core-data/src/resolvers.js': [
        (131, 'key', 'template backing post', 'compare', 'numeric vs composite template route'),
        (139, 'key', 'configured entity', 'url', 'path interpolation of a string-capable key'),
        (859, 'globalStylesURL', 'global styles post', 'parse', 'digits-only REST link extraction'),
        (860, 'id', 'global styles post', 'parse', 'Number on link capture')],
    'core-data/src/selectors.ts': [
        (65, 'EntityRecordKey', 'configured entity', 'type', 'string | number'),
        (428, 'recordKey', 'configured entity', 'parse', 'numeric-only normalization, UUID falls through')],
    'edit-site/src/components/editor/use-revisions-url-sync.js': [
        (65, 'location.query.revision', 'revision post', 'parse', 'Number on URL query revision')],
    'editor/src/components/collab-sidebar/hooks.js': [
        (149, 'thread.id', 'comment note', 'sort', 'numeric ID tie-break')],
    'editor/src/components/collab-sidebar/utils.js': [
        (111, 'value', 'comment note', 'parse', 'Number on note ID iteration value')],
    'editor/src/components/post-author/select.js': [
        (19, 'author', 'user', 'parse', 'Number on author option value')],
    'server-side-render/src/hook.ts': [
        (16, 'urlQueryArgs', 'post', 'url', 'block-renderer forwards post_id from caller')],
}
STRING_CAPABLE = {
    ('core-data/src/entities.js', 26), ('core-data/src/entities.js', 414),
    ('core-data/src/queried-data/reducer.js', 92), ('core-data/src/queried-data/reducer.js', 93),
    ('core-data/src/reducer.js', 346), ('core-data/src/reducer.js', 347),
    ('core-data/src/resolvers.js', 139), ('core-data/src/selectors.ts', 65),
    ('core-data/src/selectors.ts', 428), ('server-side-render/src/hook.ts', 16),
}


def reviewed_rows(sources):
    rows = []
    for path, sites in SITES.items():
        source = sources['packages/' + path]
        for line, key, entity, kind, current in sites:
            severity = 'breaks-with-uuid'
            change = 'Preserve and validate the complete UUID at this boundary'
            if (path, line) in STRING_CAPABLE:
                severity = 'cosmetic'
                change = 'Retain string behavior and test UUIDv7 keys end to end'
            elif kind == 'sort':
                severity = 'degrades'
                change = 'Order by explicit chronology and use a stable tie-break'
            rows.append(js_row(source, line, key, entity, kind, severity, 'high', current, change))
    # Review explicit root entity key declarations.
    source = sources['packages/core-data/src/entities.js']
    for line in (42, 76, 95, 177, 201, 211, 221, 229, 239, 249, 259, 527):
        rows.append(js_row(source, line, 'entityConfig.key', 'configured entity', 'schema',
                           'cosmetic', 'high', source.lines[line - 1].strip(),
                           'Preserve slug/composite keys and singleton behavior where configured'))
    return rows
