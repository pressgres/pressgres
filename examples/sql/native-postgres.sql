-- Illustrative excerpt, NOT a deployable complete WordPress schema.
-- PostgreSQL 18+ for uuidv7().  Preserve expected quoted ID spelling.
CREATE TABLE wp_users (
  "ID" uuid PRIMARY KEY DEFAULT uuidv7(),
  user_login varchar(60) NOT NULL UNIQUE
);
CREATE TABLE wp_posts (
  "ID" uuid PRIMARY KEY DEFAULT uuidv7(),
  post_author uuid NULL REFERENCES wp_users("ID"),
  post_parent uuid NULL REFERENCES wp_posts("ID"),
  post_title text NOT NULL DEFAULT ''
);
CREATE INDEX wp_posts_author_idx ON wp_posts(post_author);
INSERT INTO wp_users (user_login) VALUES ('example-admin') RETURNING "ID";
-- WordPress PHP must preserve returned UUID string; missing references map to NULL.
-- SELECT uuid_extract_version("ID") FROM wp_users; -- expected 7 for generated IDs.
