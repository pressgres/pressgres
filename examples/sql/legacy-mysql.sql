-- Illustrative excerpt, NOT canonical complete WordPress schema.
CREATE TABLE wp_users (
  ID bigint unsigned NOT NULL AUTO_INCREMENT,
  user_login varchar(60) NOT NULL,
  PRIMARY KEY (ID)
) ENGINE=InnoDB;
CREATE TABLE wp_posts (
  ID bigint unsigned NOT NULL AUTO_INCREMENT,
  post_author bigint unsigned NOT NULL DEFAULT 0,
  post_parent bigint unsigned NOT NULL DEFAULT 0,
  post_title text NOT NULL,
  PRIMARY KEY (ID)
) ENGINE=InnoDB;
-- WordPress often represents missing references as integer 0.
