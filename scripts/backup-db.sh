#!/bin/sh
set -eu

backup_file=${BACKUP_FILE:-"/backups/ossustain_$(date -u +%Y%m%dT%H%M%SZ).dump"}
case "$backup_file" in
    /backups/*)
        backup_name=${backup_file#/backups/}
        case "$backup_name" in
            ""|*/*|.|..) echo "BACKUP_FILE must be a filename directly inside /backups" >&2; exit 2 ;;
        esac
        ;;
    *) echo "BACKUP_FILE must be inside /backups" >&2; exit 2 ;;
esac
if [ -L "$backup_file" ]; then
    echo "Refusing to write through a backup symlink: $backup_file" >&2
    exit 2
fi
if [ -e "$backup_file" ]; then
    echo "Refusing to overwrite existing backup: $backup_file" >&2
    exit 3
fi

umask 077
pg_dump --format=custom --file="$backup_file"
test -s "$backup_file"
printf 'Database backup written to %s\n' "$backup_file"
