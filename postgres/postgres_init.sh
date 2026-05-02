#!/bin/bash
psql -U postgres -c "CREATE USER $PG_USER WITH ENCRYPTED PASSWORD '$PG_PASSWD';"
psql -U postgres -c "ALTER USER $PG_USER CREATEDB;"
psql -U postgres -c "DROP DATABASE IF EXISTS $PG_DATABASE;"
psql -U postgres -c "CREATE DATABASE $PG_DATABASE;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE $PG_DATABASE TO $PG_USER;"
psql  -U postgres -d $PG_DATABASE -c "GRANT ALL ON SCHEMA public TO $PG_USER;"
