# R-009 core PHPUnit runner image.
# PHP 8.4 CLI with the extensions the wordpress-develop suite expects
# (gd is mandatory per tests/phpunit/includes/bootstrap.php) plus both
# MySQL (control) and PostgreSQL (Pressgres prototype) client drivers.
ARG PHP_IMAGE=php:8.4.28-cli-bookworm
ARG COMPOSER_IMAGE=composer:2.11.2

FROM ${COMPOSER_IMAGE} AS composer

FROM ${PHP_IMAGE}

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libpng-dev libjpeg62-turbo-dev libwebp-dev libavif-dev libfreetype6-dev \
        libzip-dev libicu-dev libpq-dev libmagickwand-dev ghostscript \
        unzip git rsync default-mysql-client postgresql-client; \
    docker-php-ext-configure gd --with-jpeg --with-webp --with-avif --with-freetype; \
    docker-php-ext-install -j"$(nproc)" gd mysqli pdo_mysql pgsql pdo_pgsql intl zip exif bcmath opcache; \
    pecl install imagick-3.8.0; \
    docker-php-ext-enable imagick; \
    # Debian's ImageMagick policy blocks PDF; upstream image tests render PDF previews.
    sed -i '/pattern="PDF"/d' /etc/ImageMagick-6/policy.xml; \
    rm -rf /var/lib/apt/lists/* /tmp/pear

COPY --from=composer /usr/bin/composer /usr/local/bin/composer

# Pinned test tooling (PHPUnit 9.6 + Yoast polyfills 1.1), installed outside
# the WordPress tree so no vendor code ever lands in the repository.
COPY composer.json composer.lock /srv/wp-test-tools/
RUN cd /srv/wp-test-tools && composer install --no-interaction --no-progress --prefer-dist

COPY config/php.ini /usr/local/etc/php/conf.d/zz-r009.ini

ENV PATH="/srv/wp-test-tools/vendor/bin:${PATH}"
WORKDIR /srv/wordpress-develop
