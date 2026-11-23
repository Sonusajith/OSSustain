# Phase 17: Authentication and Admin Architecture Proposal

**Status:** Proposed; implementation has not started pending owner approval.

Phase 16 is merged in PR #16. Its analysis submission and status APIs are public and quota-bounded, but the project has no user identity or authorization. Phase 17 will add identity only around analysis and administration; public research reads remain public.

## Recommended scope

- Add Spring Security using the Spring Boot 4.1.2 managed dependency set.
- Use server-side sessions in PostgreSQL, with an `HttpOnly`, `SameSite=Lax` cookie; require HTTPS and `Secure` cookies in production. Keep CSRF protection enabled for state-changing requests and credentialed CORS restricted to the configured frontend origin.
- Add `RESEARCHER` and `ADMIN` roles. Disable public self-registration. Bootstrap the first administrator from deployment-provided credentials, store only a modern password hash, and require changing the bootstrap password at first sign-in.
- Keep cohort, repository, comparison, and research endpoints publicly readable. Require sign-in to submit or read an analysis. Associate jobs with their submitting account so researchers can only read their own jobs; administrators can inspect all jobs.
- Add a small admin screen and protected endpoints for creating/disabling accounts and inspecting/canceling queued or running analysis jobs. Prevent disabling the last active administrator. Record actor, action, target, and timestamp for administrative changes without storing passwords or session identifiers in audit records.
- Retain Phase 16 IP and global request limits as defense-in-depth. Do not expose GitHub credentials or change the Python worker boundary.

## Database and rollout impact

A new Flyway migration would create account, role, audit, and database-backed session tables, then associate existing `analysis_jobs` rows with an account where possible. Existing anonymous Phase 16 jobs have no account identity; retain their status and result but make them inaccessible to ordinary signed-in users. Establish explicit expiry/cleanup for these orphaned records. Do not edit V11.

New security dependencies are needed for Spring Security and JDBC-backed sessions. Versions should be managed by the project's pinned Spring Boot parent rather than adding uncoordinated version numbers. No frontend dependency is proposed; existing React forms and API client are sufficient.

## Approval choices

The owner should approve or revise these points before implementation:

1. Cookie-backed server sessions with PostgreSQL persistence, versus stateless bearer tokens.
2. Invite-only accounts bootstrapped by an environment-provided first administrator, versus public self-registration.
3. Whether admin scope includes account management and queue inspection/cancellation, as proposed.
4. Whether Phase 16 analysis submission and status become sign-in-only while all research reads stay public.

## Security verification

Tests should cover anonymous access, successful and failed login, logout/session invalidation, CSRF rejection, role checks, per-account analysis ownership, administrator operations, last-admin protection, and public read access. Production Compose and CORS behavior must be reviewed alongside those tests.
