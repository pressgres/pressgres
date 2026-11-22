# 16 — Source references and verification notes

This PRD was researched 2026-11-22. These external links are references, **not third-party licensing or compatibility certification**. Revalidate at release time.

1. WordPress 7.1 server compatibility / release metadata: <https://make.wordpress.org/hosting/handbook/compatibility/version/7-1/>
2. PHP support clarifications (WordPress 2026): <https://make.wordpress.org/core/2026/05/22/php-support-clarification-2026/>
3. WordPress PHP compatibility table: <https://make.wordpress.org/core/handbook/references/php-compatibility-and-wordpress-versions/>
4. WordPress hosting requirements: <https://wordpress.org/about/requirements/>
5. WordPress `$wpdb` / `db.php` drop-in interface: <https://developer.wordpress.org/reference/classes/wpdb/>
6. PostgreSQL 18 UUID support: <https://www.postgresql.org/docs/18/datatype-uuid.html>
7. PostgreSQL 18 UUID functions: <https://www.postgresql.org/docs/18/functions-uuid.html>
8. DDEV architecture (DB service supports PG): <https://docs.ddev.com/en/stable/users/usage/architecture/>
9. DDEV additional/custom services: <https://docs.ddev.com/en/stable/users/extend/additional-services/>
10. WordPress SQLite database integration (SQL parser/emulation reference): <https://github.com/WordPress/sqlite-database-integration>
11. PG4WP PostgreSQL for WordPress reference: <https://github.com/PostgreSQL-For-Wordpress/postgresql-for-wordpress>
12. WordPress developer plugin lifecycle hooks: <https://developer.wordpress.org/reference/hooks/upgrader_pre_install/> and <https://developer.wordpress.org/reference/hooks/upgrader_process_complete/>

## Evidence interpretation

- WordPress upstream PHP minimum is **not** Pressgres compatibility. WPS must test patched core itself.
- PG4WP is a prior art reference, not proof UUID-only WordPress works on PG.
- WordPress SQLite parser may inspire implementation; verify API and GPL compatibility before reuse.
- DDEV local PostgreSQL ability is not evidence a stock WordPress template works with it without WPS.
- No benchmark, plugin success or runtime test claims are made in this document package.
