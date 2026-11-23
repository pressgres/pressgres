-- R-003 prototype: minimal native PostgreSQL 18 schema for WordPress 7.1.5.
-- THROWAWAY. Only the tables needed to boot WordPress and create/read a post.
-- Every entity PK is uuid DEFAULT uuidv7(); every ID reference is a nullable
-- uuid (NULL replaces WordPress's legacy 0 sentinel). Mixed-case WordPress
-- column names ("ID") are quoted so PostgreSQL preserves their case.
--
-- Deliberate prototype simplifications (NOT design decisions; see report):
--   * datetime columns are varchar(19) because WordPress writes the MySQL
--     zero date '0000-00-00 00:00:00', which PostgreSQL timestamp rejects.
--   * no FK constraints (docs/04 says prototype identity first).
--   * no comments/links tables (not on the happy path).

CREATE TABLE wp_options (
  option_id    uuid PRIMARY KEY DEFAULT uuidv7(),
  option_name  varchar(191) NOT NULL DEFAULT '' UNIQUE,
  option_value text NOT NULL,
  autoload     varchar(20) NOT NULL DEFAULT 'yes'
);
CREATE INDEX wp_options_autoload_idx ON wp_options (autoload);

CREATE TABLE wp_users (
  "ID"                uuid PRIMARY KEY DEFAULT uuidv7(),
  user_login          varchar(60) NOT NULL DEFAULT '',
  user_pass           varchar(255) NOT NULL DEFAULT '',
  user_nicename       varchar(50) NOT NULL DEFAULT '',
  user_email          varchar(100) NOT NULL DEFAULT '',
  user_url            varchar(100) NOT NULL DEFAULT '',
  user_registered     varchar(19) NOT NULL DEFAULT '0000-00-00 00:00:00',
  user_activation_key varchar(255) NOT NULL DEFAULT '',
  user_status         integer NOT NULL DEFAULT 0,
  display_name        varchar(250) NOT NULL DEFAULT ''
);
CREATE INDEX wp_users_user_login_key ON wp_users (user_login);
CREATE INDEX wp_users_user_nicename ON wp_users (user_nicename);
CREATE INDEX wp_users_user_email ON wp_users (user_email);

CREATE TABLE wp_usermeta (
  umeta_id   uuid PRIMARY KEY DEFAULT uuidv7(),
  user_id    uuid NULL,
  meta_key   varchar(255) NULL,
  meta_value text NULL
);
CREATE INDEX wp_usermeta_user_id ON wp_usermeta (user_id);
CREATE INDEX wp_usermeta_meta_key ON wp_usermeta (meta_key);

CREATE TABLE wp_posts (
  "ID"                  uuid PRIMARY KEY DEFAULT uuidv7(),
  post_author           uuid NULL,
  post_date             varchar(19) NOT NULL DEFAULT '0000-00-00 00:00:00',
  post_date_gmt         varchar(19) NOT NULL DEFAULT '0000-00-00 00:00:00',
  post_content          text NOT NULL,
  post_title            text NOT NULL,
  post_excerpt          text NOT NULL,
  post_status           varchar(20) NOT NULL DEFAULT 'publish',
  comment_status        varchar(20) NOT NULL DEFAULT 'open',
  ping_status           varchar(20) NOT NULL DEFAULT 'open',
  post_password         varchar(255) NOT NULL DEFAULT '',
  post_name             varchar(200) NOT NULL DEFAULT '',
  to_ping               text NOT NULL,
  pinged                text NOT NULL,
  post_modified         varchar(19) NOT NULL DEFAULT '0000-00-00 00:00:00',
  post_modified_gmt     varchar(19) NOT NULL DEFAULT '0000-00-00 00:00:00',
  post_content_filtered text NOT NULL,
  post_parent           uuid NULL,
  guid                  varchar(255) NOT NULL DEFAULT '',
  menu_order            integer NOT NULL DEFAULT 0,
  post_type             varchar(20) NOT NULL DEFAULT 'post',
  post_mime_type        varchar(100) NOT NULL DEFAULT '',
  comment_count         bigint NOT NULL DEFAULT 0
);
CREATE INDEX wp_posts_post_name ON wp_posts (post_name);
CREATE INDEX wp_posts_type_status_date ON wp_posts (post_type, post_status, post_date, "ID");
CREATE INDEX wp_posts_post_parent ON wp_posts (post_parent);
CREATE INDEX wp_posts_post_author ON wp_posts (post_author);

CREATE TABLE wp_postmeta (
  meta_id    uuid PRIMARY KEY DEFAULT uuidv7(),
  post_id    uuid NULL,
  meta_key   varchar(255) NULL,
  meta_value text NULL
);
CREATE INDEX wp_postmeta_post_id ON wp_postmeta (post_id);
CREATE INDEX wp_postmeta_meta_key ON wp_postmeta (meta_key);

CREATE TABLE wp_terms (
  term_id    uuid PRIMARY KEY DEFAULT uuidv7(),
  name       varchar(200) NOT NULL DEFAULT '',
  slug       varchar(200) NOT NULL DEFAULT '',
  term_group bigint NOT NULL DEFAULT 0
);
CREATE INDEX wp_terms_slug ON wp_terms (slug);
CREATE INDEX wp_terms_name ON wp_terms (name);

CREATE TABLE wp_term_taxonomy (
  term_taxonomy_id uuid PRIMARY KEY DEFAULT uuidv7(),
  term_id          uuid NULL,
  taxonomy         varchar(32) NOT NULL DEFAULT '',
  description      text NOT NULL,
  parent           uuid NULL,
  count            bigint NOT NULL DEFAULT 0,
  UNIQUE (term_id, taxonomy)
);
CREATE INDEX wp_term_taxonomy_taxonomy ON wp_term_taxonomy (taxonomy);

CREATE TABLE wp_term_relationships (
  object_id        uuid NOT NULL,
  term_taxonomy_id uuid NOT NULL,
  term_order       integer NOT NULL DEFAULT 0,
  PRIMARY KEY (object_id, term_taxonomy_id)
);
CREATE INDEX wp_term_relationships_tt ON wp_term_relationships (term_taxonomy_id);

CREATE TABLE wp_termmeta (
  meta_id    uuid PRIMARY KEY DEFAULT uuidv7(),
  term_id    uuid NULL,
  meta_key   varchar(255) NULL,
  meta_value text NULL
);
CREATE INDEX wp_termmeta_term_id ON wp_termmeta (term_id);
CREATE INDEX wp_termmeta_meta_key ON wp_termmeta (meta_key);
