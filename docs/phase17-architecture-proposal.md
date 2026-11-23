# Phase 17: Authentication and Admin Architecture Proposal

**Status:** Approved by the project owner and implemented on `phase-17/auth-admin`; awaiting pull request review and merge.

Phase 16 is merged in PR #16. Its analysis submission and status APIs are public and quota-bounded, but the project has no user identity or authorization. Phase 17 will add identity only around analysis and administration; public research reads remain public.

## Approved scope and implementation

- Add Spring Security using the Spring Boot 4.1.2 managed dependency set.
- Use server-side sessions in PostgreSQL, with an `HttpOnly`, `SameSite=Lax` cookie; require HTTPS and `Secure` cookies in production. Keep CSRF protection enabled for state-changing requests and credentialed CORS restricted to the configured frontend origin.
- Add `RESEARCHER` and `ADMIN` roles. Disable public self-registration. Bootstrap the first administrator from deployment-provided credentials, store only a modern password hash, and require changing the bootstrap password at first sign-in.
- Keep cohort, repository, comparison, and research endpoints publicly readable. Require sign-in to submit or read an analysis. Associate jobs with their submitting account so researchers can only read their own jobs; administrators can inspect all jobs.
- Add a small admin screen and protected endpoints for creating/disabling accounts and inspecting/canceling queued or running analysis jobs. Prevent disabling the last active administrator. Record actor, action, target, and timestamp for administrative changes without storing passwords or session identifiers in audit records.
- Retain Phase 16 IP and global request limits as defense-in-depth. Do not expose GitHub credentials or change the Python worker boundary.
- Require a valid CSRF token for state-changing session requests. Clear sessions when an account is disabled, enforce HTTPS-only secure cookies in production, and serialize last-admin disable checks.

## Database and rollout impact

A new Flyway migration would create account, role, audit, and database-backed session tables, then associate existing `analysis_jobs` rows with an account where possible. Existing anonymous Phase 16 jobs have no account identity; retain their status and result but make them inaccessible to ordinary signed-in users. Establish explicit expiry/cleanup for these orphaned records. Do not edit V11.

New security dependencies are needed for Spring Security and JDBC-backed sessions. Versions should be managed by the project's pinned Spring Boot parent rather than adding uncoordinated version numbers. No frontend dependency is proposed; existing React forms and API client are sufficient.

## Implementation details

- Flyway V12 adds accounts, `ADMIN`/`RESEARCHER` roles, audit events, account ownership for new analyses, and PostgreSQL-backed Spring Session tables. Existing anonymous Phase 16 jobs remain visible only to administrators and retain the worker's 30-day cleanup behavior.
- First-admin credentials come from `OSSUSTAIN_ADMIN_USERNAME` and `OSSUSTAIN_ADMIN_PASSWORD`; the password must have at least 16 characters. A bootstrap or newly issued temporary password must be changed after sign-in. The server stores BCrypt hashes, not readable passwords.
- State-changing requests use CSRF tokens. Sessions expire after 30 minutes; cookies are HttpOnly and SameSite=Lax. Production Compose sets `SESSION_COOKIE_SECURE=true`.
- `GET /api/v1/auth/csrf`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/password`, and `POST /api/v1/auth/logout` manage sessions. `POST /api/v1/admin/users`, `GET /api/v1/admin/users`, `PATCH /api/v1/admin/users/{id}/enabled`, `GET /api/v1/admin/analyses`, and `POST /api/v1/admin/analyses/{id}/cancel` are administrator-only.
- Research read endpoints stay public. Analysis submission/status require sign-in; a researcher can read only jobs linked to their account. Disabled accounts have their stored sessions removed. Last active administrator protection is serialized across concurrent requests.
- Backend uses Spring Boot-managed `spring-boot-starter-security`, `spring-boot-starter-session-jdbc`, and `spring-boot-starter-validation` dependencies. The Python worker change prevents a canceled job from being overwritten by a later worker completion.

## Security verification

Testcontainers tests cover anonymous access, login and password change, logout/session invalidation, CSRF-protected writes, role checks, per-account analysis ownership, administrator operations, last-admin protection, and public read access. Production Compose and CORS behavior are reviewed alongside those tests.
