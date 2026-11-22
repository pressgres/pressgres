"""Source-reviewed REST URL, coercion, and generated schema sites."""
from audit import ENDPOINTS, REST, Source, rest_row

# Controller or source file, source line, property, related entity.
LINKS = {
    'application-passwords': [(663, 'self.user_id', 'user')],
    'attachments': [(637, 'Location', 'attachment'), (789, 'Location', 'attachment'),
                    (1374, 'Location', 'attachment'), (1700, 'up', 'post'),
                    (3447, 'attachment route', 'attachment')],
    'autosaves': [(485, 'preview_link', 'post and autosave revision')],
    'comments': [(858, 'Location', 'comment'), (1246, 'link', 'comment'),
                 (1301, 'self', 'comment'), (1310, 'author', 'user'),
                 (1321, 'up', 'post'), (1330, 'in-reply-to', 'comment'),
                 (1349, 'children.parent', 'comment'), (1365, 'children.parent (notes)', 'comment')],
    'font-faces': [(805, 'self', 'font family and face posts'), (808, 'collection', 'font family post'),
                   (811, 'parent', 'font family post')],
    'font-families': [(508, 'font_faces', 'font family and face posts')],
    'global-styles': [(397, 'self', 'global styles post'), (407, 'version-history', 'global styles post')],
    'global-styles-revisions': [(264, 'pagination.parent', 'global styles post')],
    'menu-items': [(205, 'Location', 'menu item post'), (677, 'related', 'post'),
                   (680, 'related', 'term'), (704, 'targetHints.{id}', 'menu item post')],
    'menu-locations': [(247, 'menu', 'menu term')],
    'menus': [(280, 'Location', 'menu term')],
    'navigation-fallback': [(186, 'self', 'navigation post')],
    'posts': [(673, 'Link alternate', 'post'), (880, 'Location', 'post'), (1969, 'link', 'post'),
              (2126, 'permalink_template', 'post'), (2228, 'self', 'post'), (2241, 'author', 'user'),
              (2248, 'replies.post', 'post'), (2259, 'version-history', 'post'),
              (2268, 'predecessor-version', 'revision post'), (2278, 'up', 'parent post'),
              (2286, 'featuredmedia', 'attachment'), (2296, 'attachment.parent', 'post'),
              (2315, 'term.post', 'post'), (2847, 'targetHints.{id}', 'post')],
    'revisions': [(384, 'pagination.parent', 'post'), (725, 'parent', 'post')],
    'template-autosaves': [(255, 'self', 'template autosave revision post')],
    'template-revisions': [(278, 'self', 'template revision post')],
    'templates': [(987, 'predecessor-version', 'template revision post')],
    'terms': [(630, 'Location', 'taxonomy term'), (925, 'link', 'taxonomy term'),
              (990, 'self', 'taxonomy term'),
              (1005, 'up', 'parent term'), (1027, 'post-type query filter', 'taxonomy term')],
    'themes': [(417, 'global-styles', 'global styles post')],
    'users': [(706, 'Location', 'user'), (1156, 'self', 'user')],
    'src/wp-admin/edit-form-blocks.php': [(52, 'editor preload', 'post')],
    'src/wp-admin/site-editor.php': [(243, 'site editor preload', 'post')],
    'src/wp-includes/rest-api.php': [(3247, 'rest_get_route_for_post', 'post'),
                                   (3315, 'rest_get_route_for_term', 'taxonomy term'),
                                   (3370, 'discovery', 'post'), (3372, 'discovery', 'taxonomy term')],
    REST + '/search/class-wp-rest-post-search-handler.php': [(172, 'self', 'post')],
    REST + '/search/class-wp-rest-term-search-handler.php': [(169, 'self', 'taxonomy term')],
    REST + '/class-wp-rest-server.php': [(1524, 'site_logo', 'attachment')],
}
SANITIZERS = {
    'users': [(935, 'reassign', 'user'), (1194, 'id', 'user')],
    'menu-items': [(417, 'menus', 'menu term'), (435, 'object_id', 'taxonomy term'),
                   (443, 'object_id', 'post'), (571, 'object_id response', 'post or taxonomy term')],
    'pattern-directory': [(197, 'id', 'upstream pattern directory record')],
}

# Selected controller logic beyond declared request sanitizers.
CASTS = {
    'application-passwords': [(709, 'user_id', 'user')],
    'attachments': [(420, 'post', 'post'), (1409, 'post', 'post'), (1509, 'post', 'post'),
                    (2753, 'id', 'attachment'), (3248, 'id', 'attachment')],
    'block-renderer': [(114, 'post_id', 'post'), (156, 'post_id', 'post')],
    'comments': [(401, 'id', 'comment'), (405, 'id', 'comment'), (564, 'post', 'post'),
                 (1194, 'id', 'comment'), (1198, 'post', 'post'), (1202, 'parent', 'comment'),
                 (1206, 'author', 'user'), (1328, 'parent', 'comment')],
    'font-faces': [(305, 'parent', 'font family post'), (419, 'parent', 'font family post'),
                   (778, 'font_family_id', 'font family post'), (782, 'font_family_id', 'font family post')],
    'global-styles': [(145, 'id', 'global styles post')],
    'menu-locations': [(198, 'menu', 'menu term')],
    'navigation-fallback': [(158, 'id', 'navigation post')],
    'posts': [(560, 'id', 'post'), (564, 'id', 'post'), (1396, 'author', 'user'),
              (1447, 'parent', 'post'), (1450, 'parent', 'post'), (1614, 'featured_media', 'attachment'),
              (1744, 'terms', 'taxonomy term'), (2056, 'author', 'user'),
              (2060, 'featured_media', 'attachment'), (2064, 'parent', 'post')],
    'revisions': [(157, 'parent', 'post'), (212, 'id', 'revision post'), (439, 'parent', 'post')],
    'templates': [(643, 'author', 'user'), (760, 'wp_id', 'template backing post')],
    'terms': [(432, 'id', 'taxonomy term'), (436, 'id', 'taxonomy term'),
              (913, 'id', 'taxonomy term'), (941, 'parent', 'taxonomy term')],
    'users': [(451, 'id', 'user'), (455, 'id', 'user')],
}


def evidence_rows(root):
    rows = []
    for name, sites in LINKS.items():
        path = name if '/' in name else ENDPOINTS + name + '-controller.php'
        source = Source(root, root / path)
        for line, key, entity in sites:
            evidence = source.lines[line - 1].strip()
            numeric = '%d' in evidence
            route = None
            if name == 'src/wp-includes/rest-api.php':
                route = '/wp/v2/{taxonomy-base}/{id}' if 'term' in entity else '/wp/v2/{post-base}/{id}'
            elif name.startswith('src/wp-admin/'):
                route = '/wp/v2/{post-base}/{id}'
            elif 'search-handler' in name:
                route = '/wp/v2/search'
            elif name.endswith('server.php'):
                route = '/'
            rows.append(rest_row(
                source, line, 'link', key, '%d' if numeric else 'ID in path, query, or template',
                'Format the complete UUID as a path segment' if numeric else
                'Preserve the complete UUID and verify the destination route or query schema',
                entity=entity, route=route, severity='breaks-with-uuid' if numeric else 'degrades',
            ))
    for name, sites in SANITIZERS.items():
        source = Source(root, root / (ENDPOINTS + name + '-controller.php'))
        for line, key, entity in sites:
            external = name == 'pattern-directory'
            rows.append(rest_row(
                source, line, 'sanitize', key, 'absint()',
                'Preserve upstream external ID' if external else
                'Validate canonical UUID and preserve field-specific missing semantics',
                entity=entity, severity='cosmetic' if external else 'breaks-with-uuid',
            ))
    for name, sites in CASTS.items():
        source = Source(root, root / (ENDPOINTS + name + '-controller.php'))
        for line, key, entity in sites:
            assert '(int)' in source.lines[line - 1]
            rows.append(rest_row(
                source, line, 'coercion', key, '(int)',
                'Carry a validated UUID through lookup, comparison, permission check, or response',
                entity=entity,
            ))
    source = Source(root, root / 'src/wp-includes/option.php')
    for line, key, entity in ((2875, 'default_category', 'category term'),
                              (2918, 'page_on_front', 'page'), (2929, 'page_for_posts', 'page')):
        rows.append(rest_row(
            source, line, 'schema', key, 'integer',
            'Change registered option schema and repair its consumer and missing-value handling',
            entity=entity, route='/wp/v2/settings',
            evidence=source.lines[line - 1].strip() + ' exposed by ' +
            root.name + '/' + ENDPOINTS + 'settings-controller.php:220',
        ))
    return rows
