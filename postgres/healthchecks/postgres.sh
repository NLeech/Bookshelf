#!/bin/bash
set -eo pipefail

host="$(hostname -i || echo '127.0.0.1')"
user="${PG_USER:-postgres}"
db="${PG_DATABASE:-$POSTGRES_USER}"
export PGPASSWORD="${PG_PASSWD:-}"

args=(
	# force postgres to not use the local unix socket (test "external" connectibility)
	--host "$host"
	--username "$user"
	--dbname "$db"
	--quiet --no-align --tuples-only
)

if select="$(echo 'SELECT 1' | psql "${args[@]}")" && [ "$select" = '1' ]; then
	exit 0
fi

exit 1