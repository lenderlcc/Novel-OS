#!/bin/sh
set -eu

config_dir=/run/novel-postgres
data_dir=/var/lib/postgresql/data
username=$(cat "$config_dir/username")
database=$(cat "$config_dir/database")

if [ "${1:-}" = healthcheck ]; then
    exec pg_isready -h 127.0.0.1 -p 5432 -U "$username" -d "$database"
fi

if [ "$(id -u)" = 0 ]; then
    mkdir -p "$data_dir"
    chown postgres:postgres "$data_dir"
    chmod 700 "$data_dir"
    exec gosu postgres sh "$0"
fi

if [ ! -s "$data_dir/PG_VERSION" ]; then
    initdb -D "$data_dir" --username="$username" --pwfile="$config_dir/password" \
        --auth-local=trust --auth-host=scram-sha-256 --encoding=UTF8
    printf '\nhost all all all scram-sha-256\n' >> "$data_dir/pg_hba.conf"
    # The temporary server accepts only Unix socket connections during setup.
    pg_ctl -D "$data_dir" -o "-c listen_addresses='' -c unix_socket_directories=/tmp" -w start
    trap 'pg_ctl -D "$data_dir" -m fast -w stop' EXIT
    if [ "$database" != postgres ]; then
        createdb -h /tmp -U "$username" -- "$database"
    fi
    pg_ctl -D "$data_dir" -m fast -w stop
    trap - EXIT
fi

exec postgres -D "$data_dir" -c listen_addresses='*' -c unix_socket_directories=/tmp
