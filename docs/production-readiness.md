# Production deployment and operations

Phase 13 provides a local, containerized deployment template. No public hosting
provider or production domain has been selected. Put a TLS reverse proxy in
front of the frontend before exposing the service publicly; PostgreSQL and the
backend are not published to the host.

## Deploy

Requirements: Docker Engine with Compose v2. From the repository root:

```powershell
Copy-Item deploy/production.env.example deploy/.env.production
```

Edit `deploy/.env.production`: replace `POSTGRES_PASSWORD` with a long random
secret and set `FRONTEND_URL`, `FRONTEND_ORIGIN`, and `HTTP_PORT` to the URL and
port users will access. Keep this file private. Then start the production stack:

```powershell
docker compose --env-file deploy/.env.production -f compose.production.yaml up -d --build
docker compose --env-file deploy/.env.production -f compose.production.yaml ps
```

Open `FRONTEND_URL`. The frontend proxies API calls to the internal backend.
The backend waits for PostgreSQL health and applies Flyway migrations at start.
Only the frontend port is published. Logs are available with:

```powershell
docker compose --env-file deploy/.env.production -f compose.production.yaml logs --tail 200
```

The normal development database remains separate and is still started with
`docker compose up -d postgres`.

## Back up and restore

Create the configured backup directory on the host, then run a custom-format
PostgreSQL dump. `BACKUP_FILE` can name a specific file under `/backups` or be
left empty to use a UTC timestamp. The backup command refuses to overwrite an
existing file or follow a symlink:

```powershell
New-Item -ItemType Directory -Force backups
docker compose --env-file deploy/.env.production -f compose.production.yaml --profile ops run --rm db-backup
```

For restore, use a new database name. Restore refuses to overwrite an existing
database and only reads paths under the mounted backup folder:

```powershell
docker compose --env-file deploy/.env.production -f compose.production.yaml --profile ops run --rm `
  -e RESTORE_DATABASE=ossustain_restore_check `
  -e BACKUP_FILE=/backups/ossustain_YYYYMMDDTHHMMSSZ.dump db-restore
```

After validating the restored data, use a planned database migration procedure
to adopt it. These scripts do not delete backups or existing databases. Protect
and copy backup files off the deployment host according to the team's retention
policy; none is set by this project.

## Checks and security

The pull request workflow runs Python tests/lint and `pip-audit`, Maven tests,
frontend lint/tests/build and production dependency audit, and builds both
container images. GitHub Actions are pinned to full commit SHAs, and Dependabot
checks pinned dependencies weekly. Resolve high or critical audit findings
before release; document medium findings and assess whether they apply.

The production Compose file keeps database/backend ports private, uses health
checks, non-root application users, read-only application filesystems, dropped
Linux capabilities, and no-new-privileges. Supply secrets through the private
environment file or a deployment secret manager. The API currently has no user
authentication and is intended for trusted research deployment behind an
appropriately restricted network boundary.

## Accessibility and performance review

The existing UI implements semantic headings and tables, loading/empty/error
states, keyboard operation, and text alternatives for data visualizations. Do
a keyboard-only walkthrough and run Lighthouse against the deployed URL before
release. Record the tested URL, device profile, Lighthouse scores, and any
accessibility findings here; no hosted target is configured, so this repository
does not claim a production Lighthouse score. The local production build emits
359.26 kB of JavaScript (106.85 kB gzip), 27.29 kB CSS (5.79 kB gzip), and a
0.54 kB HTML entry (0.34 kB gzip). Treat these as bundle-size measurements,
not page-load performance scores.\n