# AGENTS.md: OSSustain AI Agent Instructions

This file is read automatically by AI coding agents (e.g., Codex) at the start of every session. It applies to **every** person and every agent working on this repository. OSSustain is a **team project**: several people and agents may work on it at different times. Follow these instructions exactly so that work continues cleanly from where the previous person or agent stopped, without conflicts.

## 1. Project Context

OSSustain is an early-warning system that estimates the risk of significant contribution-activity decline over the next 90 days for public GitHub repositories.

Stack: Python pipeline → PostgreSQL → Spring Boot read API → React + TypeScript dashboard.

Project documents (project root):

| File | Purpose |
|---|---|
| `PRD.md` | What to build, MVP scope, acceptance criteria |
| `Architecture.md` | Stack, data model, API, proposed folder structure |
| `Rules.md` | Coding rules |
| `Phases.md` | Ordered development phases and the current phase |
| `Memory.md` | Current progress and handoff notes (shared by the whole team) |
| `UIUX/` | Google Stitch designs (design and implementation input, not production code) |

## 2. Session Start Checklist (mandatory, in this order)

Do not write or modify any code until all steps are done.

1. **Check the Git state:**
   - `git status` : if there are uncommitted local changes, tell the user and do not overwrite them.
   - `git branch --show-current` : note the current branch.
   - `git remote -v` : confirm a GitHub remote exists. If none exists, tell the user and stop.
2. **Fetch remote changes:**
   - `git fetch --all --prune`
   - `git log --oneline HEAD..origin/<current-branch>` : see commits made by others that you do not have yet.
   - `git log --oneline origin/main -20` and `git branch -r` : see recent activity and other active branches.
   - `git diff --stat HEAD..origin/<current-branch>` : see which files others changed.
3. **Sync before working:**
   - If the remote has new commits on your branch, run `git pull --rebase origin <current-branch>` (or merge if the team prefers; do not mix styles within one branch).
   - If `main` has moved ahead of your feature branch, rebase or merge `main` into your branch before continuing.
   - If a conflict occurs, **stop**. Show the user the conflicting files and ask how to resolve. Never resolve conflicts by discarding someone else's work.
4. **Read the shared state after syncing** (never before, because the files may have changed):
   - `Memory.md` (where the team stopped, blockers, known bugs, recommended next action)
   - `Phases.md` (current phase)
   - `PRD.md`, `Architecture.md`, `Rules.md`
   - Open issues or pull requests on GitHub, if the GitHub CLI (`gh`) is available: `gh pr list` and `gh issue list`.
5. **Inspect the real project:** list the folders and files that actually exist. Do not assume anything described in the docs already exists.
6. **Report to the user** before coding:
   - What changed on the remote since the last local sync (who/what, in short).
   - The current phase and the last completed task according to `Memory.md`.
   - The task you propose to do next, and which files it will touch.
   - Wait for confirmation if there is any doubt about what to do.

## 3. Continuing Someone Else's Work

- `Memory.md` is the handoff. Continue from its **Current Task**, **Features In Progress** and **Recommended Next Action**. Do not restart or redo finished work.
- If `Memory.md` and the actual code disagree, trust the actual code and Git history, then correct `Memory.md` and tell the user.
- Never reimplement something that already exists. Search the repository first (code, tests, config, migrations).
- If another person's branch or open pull request already covers the task, do not duplicate it. Tell the user and ask.
- Never change the current phase, or begin the next phase, unless the previous one meets its Definition of Done in `Phases.md` and the user confirms.

## 4. Branching and Commit Workflow

- **Never commit directly to `main`.** Work on a feature branch named `phase-<number>/<short-task-name>` (for example, `phase-3/commit-collector`). If the user is already on a suitable branch, continue on it.
- Before creating a branch: sync `main` (`git fetch`, then branch from the latest `origin/main`).
- Make small, focused commits with clear messages: `<area>: <what changed>` (for example, `pipeline: add resumable commit collector`).
- Do not commit: secrets, `.env`, tokens, raw data caches (`data/`), model artifacts (`pipeline/artifacts/`), `node_modules`, build output.
- **Before finishing a session or any commit/push, sync again:**
  1. `git fetch --all --prune`
  2. Rebase or merge the latest remote changes into your branch.
  3. Run the tests for the code you touched.
  4. Update `Memory.md` (see Section 6).
  5. Commit and push: `git push origin <branch>`.
  6. Open or update a pull request into `main` (use `gh pr create` if available; otherwise tell the user the branch name and a suggested PR description).
- Never use `git push --force` on shared branches, `git reset --hard` on work you did not create, or any command that discards others' changes without explicit user approval.
- Do not rewrite shared history.

## 5. Avoiding Conflicts

- Re-run `git fetch` and check `git diff --stat HEAD..origin/<branch>` again right **before** editing files that are shared or frequently changed:
  - Flyway migrations (`backend/src/main/resources/db/migration/`)
  - `config/*.yaml`
  - `package.json`, `pom.xml`, `pyproject.toml` and lock files
  - `Memory.md`, `Phases.md`
  - OpenAPI/generated API types
- **Database migrations:** before creating a new Flyway migration, list the existing migration files after syncing and use the next unused version number. If two migrations share a version number after a merge, stop and ask the user. Never edit a migration that has already been merged or applied; add a new one.
- Do not make large unrelated refactors, mass renames, or reformatting of files outside the current task. These create conflicts for teammates.
- Keep changes inside the area of the current phase and task.
- If the user asks for something that overlaps with another person's open branch or pull request, warn them first.

## 6. Updating Memory.md (shared handoff)

`Memory.md` is how the next person or agent continues. It is tracked in Git and shared by the team.

- Update it after: completing a meaningful feature, an architectural decision, a database change, adding an important dependency, discovering a major bug, creating a workaround, integrating or changing a UI screen, before ending a major session, and before changing phases.
- Keep it concise. Replace outdated entries; do not append a diary.
- Before editing it, fetch and sync so you edit the latest version. When merging, preserve other people's entries and combine rather than overwrite.
- Always fill in: Current Phase, Current Task, Last Completed Task, Features In Progress, Pending Tasks, Known Bugs, Current Blockers, Recommended Next Action, Last Updated (date, branch, short note).
- Commit and push `Memory.md` together with the work it describes so the handoff is never behind the code.

## 7. Development Rules (summary; full detail in Rules.md)

- Work on **one phase at a time**, in the order of `Phases.md`.
- Follow `Architecture.md`: modular monolith plus an offline Python pipeline; Spring Boot only reads precomputed results; no microservices, queues, Redis, Redux or extra databases without approved changes.
- Schema changes only through Flyway migrations in `backend/`. The Python pipeline never runs DDL.
- Data-leakage prevention is the top technical priority: features use only data strictly before the prediction date; chronological splits only; never use the test split for selection or tuning.
- Never invent files, features, endpoints or results. Never say something works unless you ran it and verified it.
- No new dependencies, services or architecture changes without explaining them to the user first and getting approval. Record approved dependencies in `Memory.md`.
- Secrets only through environment variables. Keep `.env.example` current. Never commit tokens.
- Write and run tests as required by `Rules.md`. Never delete or weaken tests to make them pass.
- Report results honestly, including when extended features do not improve prediction.

## 8. UI/UX Rules (UIUX folder)

- `UIUX/` is the single location for Google Stitch design references (it replaces the `frontend/stitch-imports/` path mentioned in `Architecture.md` and `Rules.md`).
- Treat its contents as design and implementation input, not production code. Do not edit or delete other people's design files; add new files instead.
- Review a screen's design before building it. Preserve its visual appearance. Do not redesign it or add a competing design system.
- Integrate each screen in its own phase (Cohort Overview: Phase 10; Repository Detail: Phase 11; Research Results and Methodology & Limitations: Phase 12).
- Break generated UI code into reusable components, remove duplication, replace placeholder data with the typed API client and TanStack Query, and connect all interactions to real logic.
- Every data-driven screen needs loading, empty, error and success states, keyboard access, semantic HTML, a table or text alternative for every chart, risk category never shown by color alone, and a layout usable from 360 px width.
- If a design is missing, build a functional minimally styled version and mark the screen as pending in `Memory.md`.
- If a design conflicts with `PRD.md`, follow `PRD.md` and tell the user. If it conflicts with `Architecture.md`, keep the visual intent and adapt the implementation.

## 9. End-of-Session Report

When you stop (task done, phase done, or session ending), reply with:

1. What was built or changed (short).
2. Git status: branch name, commits pushed, pull request link or suggested PR text.
3. How to run and test it (exact commands) and the actual test results.
4. What others should know: conflicts risk, unfinished work, blockers, decisions needed.
5. The updated recommended next action.

Then stop and wait for the user's confirmation before starting anything new.
