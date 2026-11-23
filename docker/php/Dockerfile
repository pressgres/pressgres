# Pressgres development PHP runtime (I-006, ADR-0005).
# PHP 8.4 FPM + CLI with the extensions from the installer preflight list
# (docs/03-installer-cli.md, docs/07-compatibility.md). Dev/CI image only:
# no secrets, no WordPress code baked in.
ARG PHP_IMAGE=php:8.4.28-fpm-trixie@sha256:495ab94788034640ddd6fb313476e75570261622c42704e5ae02047b8d934ea0
ARG COMPOSER_IMAGE=composer:2.11.2@sha256:50ea4d33fdcde1adb0f045547295faa1548b33872e5f789dae5b02ce2fb5de93

FROM ${COMPOSER_IMAGE} AS composer

FROM ${PHP_IMAGE}

# PhpRedis is the only release cache client (ADR-0010).
ARG PHPREDIS_VERSION=6.3.0

# Bundled in the official image already: json, mbstring, curl, openssl, dom,
# xml, fileinfo, sodium. Added here: pdo_pgsql, pgsql, intl, zip, opcache,
# redis (PhpRedis).
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libpq5 libpq-dev libicu76 libicu-dev libzip5 libzip-dev \
        libfcgi-bin postgresql-client unzip git; \
    docker-php-ext-install -j"$(nproc)" pdo_pgsql pgsql intl zip opcache; \
    pecl install "redis-${PHPREDIS_VERSION}"; \
    docker-php-ext-enable redis; \
    apt-get purge -y --auto-remove libpq-dev libicu-dev libzip-dev; \
    rm -rf /var/lib/apt/lists/* /tmp/pear; \
    php -m > /tmp/php-modules; \
    for ext in pdo_pgsql pgsql redis json mbstring curl openssl dom xml zip intl fileinfo sodium "Zend OPcache"; do \
        grep -qix "$ext" /tmp/php-modules || { echo "missing extension: $ext" >&2; exit 1; }; \
    done; \
    rm /tmp/php-modules

COPY --from=composer /usr/bin/composer /usr/local/bin/composer
COPY php.ini /usr/local/etc/php/conf.d/zz-pressgres.ini
COPY fpm-pool.conf /usr/local/etc/php-fpm.d/zz-pressgres.conf
COPY --chmod=0755 fpm-healthcheck.sh /usr/local/bin/fpm-healthcheck

WORKDIR /srv/pressgres
