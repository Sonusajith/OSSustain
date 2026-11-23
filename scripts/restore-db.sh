#!/bin/sh
set -eu

: "${RESTORE_DATABASE:?Set RESTORE_DATABASE to a new, unused database name}"
: "${BACKUP_FILE:?Set BACKUP_FILE to a dump under /backups}"

case "$BACKUP_FILE" in
    /backups/*)
        backup_name=${BACKUP_FILE#/backups/}
        case "$backup_name" in
            ""|*/*|.|..) echo "BACKUP_FILE must be a filename directly inside /backups" >&2; exit 2 ;;
        esac
        ;;
    *) echo "BACKUP_FILE must be inside /backups" >&2; exit 2 ;;
esac
if ! printf '%s' "$RESTORE_DATABASE" | grep -Eq '^[A-Za-z][A-Za-z0-9_]{0,62}$'; then
    echo "RESTORE_DATABASE must start with a letter and contain only letters, digits, or underscores" >&2
    exit 2
fi
if [ ! -s "$BACKUP_FILE" ]; then
    echo "Backup file is missing or empty: $BACKUP_FILE" >&2
    exit 2
fi
if [ -L "$BACKUP_FILE" ]; then
    echo "Refusing to read through a backup symlink: $BACKUP_FILE" >&2
    exit 2
fi

existing=$(psql --dbname=postgres --no-psqlrc --tuples-only --no-align \
    --command="SELECT 1 FROM pg_database WHERE datname = '$RESTORE_DATABASE'")
if [ "$existing" = "1" ]; then
    echo "Refusing to overwrite existing database: $RESTORE_DATABASE" >&2
    exit 3
fi

createdb --maintenance-db=postgres "$RESTORE_DATABASE"
pg_restore --no-owner --no-privileges --dbname="$RESTORE_DATABASE" "$BACKUP_FILE"
printf 'Database restored to new database %s\n' "$RESTORE_DATABASE"
