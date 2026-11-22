# R-003 prototype PHP runtime: PHP 8.4 CLI + pdo_pgsql. Throwaway.
FROM php:8.4.27-cli-alpine
RUN apk add --no-cache libpq \
 && apk add --no-cache --virtual .build-deps postgresql-dev \
 && docker-php-ext-install pdo_pgsql \
 && apk del .build-deps \
 && php -m | grep -q pdo_pgsql
WORKDIR /r003
