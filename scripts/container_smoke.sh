#!/bin/sh
set -eu

SMOKE_ROOT=./var/smoke

compose() {
    docker compose \
        --project-name omra-smoke \
        -f compose.yaml \
        -f compose.smoke.yaml \
        "$@"
}

cleanup() {
    compose down --volumes --remove-orphans || true
}
trap cleanup EXIT INT TERM

cleanup
rm -rf ./var/smoke
mkdir -p "$SMOKE_ROOT/replica" "$SMOKE_ROOT/restore"
chmod 0777 "$SMOKE_ROOT/replica" "$SMOKE_ROOT/restore"

compose config --quiet
compose config --format json | python3 -c 'import json, sys; services = json.load(sys.stdin)["services"]; assert services["app"].get("environment") == {"OMRA__RUNTIME__ROLE": "app"} and not services["litestream"].get("environment"), "credential environment leaked into smoke compose"'
compose build --pull app
compose up --detach --wait --wait-timeout 180 app litestream

compose exec -T app python -c 'import sqlite3; connection = sqlite3.connect("/app/var/db/omra.sqlite"); connection.execute("CREATE TABLE smoke_probe (value TEXT NOT NULL)"); connection.execute("INSERT INTO smoke_probe VALUES (?)", ("smoke-sentinel",)); connection.commit(); connection.close()'

compose stop -t 45 litestream
compose run --rm --no-deps litestream \
    replicate -config /etc/litestream.yml -once -force-snapshot
compose run --rm --no-deps litestream \
    restore -config /etc/litestream.yml -integrity-check full \
    -o /restore/omra.sqlite /app/var/db/omra.sqlite

compose run --rm --no-deps \
    -v "$PWD/var/smoke/restore:/restore:ro" \
    app python -c 'import sqlite3; connection = sqlite3.connect("file:/restore/omra.sqlite?mode=ro", uri=True); assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",); assert connection.execute("SELECT value FROM smoke_probe").fetchone() == ("smoke-sentinel",); connection.close()'
