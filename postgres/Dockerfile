FROM postgres:15-alpine

COPY healthchecks healthchecks

COPY postgres_init.sh /docker-entrypoint-initdb.d/postgres_init.sh
