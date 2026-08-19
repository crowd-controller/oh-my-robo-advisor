# M0 Production Container Runtime Implementation Plan

> **Kanban unit:** GitHub issue #46 only. Do not begin the next roadmap card in this session.

**Goal:** Build a reproducible, least-privileged Docker Compose runtime that can prove the
application configuration, SQLite schema, writable-volume boundaries, and Litestream sidecar are
ready without pretending that the later M3 operational health catalogue already exists.

**Architecture:** Keep the canonical three-service sidecar topology: `app` owns the only live
SQLite writer, `litestream` shares only the database volume, and profile-only `tools` has neither
the live database nor broker credentials. A small M0 composition root validates the public dry-run
configuration bundle, initializes only an empty database, verifies Alembic head, and then exposes a
network-free `/readyz`. The final `/healthz`/`HealthReport` remains owned by the M3 monitoring card.
Container smoke tests use a file replica; credentialed S3 and disaster-recovery evidence remain
explicit operational gates.

**Tech stack:** Python 3.12, Typer, FastAPI/Uvicorn, HTTPX, SQLAlchemy/Alembic, Docker Compose,
Litestream v0.5, pytest, GitHub Actions.

---

## Task 1: Lock the public dry-run configuration bundle

**Files:**

- Create: `config/config.yaml`
- Create: `config/universe.yaml`
- Create: `config/goals.yaml`
- Create: `config/market_weights.yaml`
- Create: `config/external_schedules.yaml`
- Create: `config/external_income.yaml`
- Create: `config/surveillance.yaml`
- Create: `config/secrets_registry.yaml`
- Modify: `config/tr_ids.kis.yaml` only if dry-run validation requires a documented marker change
- Create: `tests/unit/config/test_repository_bundle.py`

1. Add a failing test that loads the checked-in `config/` with a fixed `SimClock` and asserts a
   valid `dry_run` `ConfigBundle`, zero accounts, no secret values, and deterministic fingerprints.
2. Run `pytest tests/unit/config/test_repository_bundle.py -q` and record the expected missing-file
   failure.
3. Add the smallest public, credential-free YAML records using existing schema defaults. Keep every
   unresolved live/paper broker value explicit; do not invent endpoints or TR IDs.
4. Re-run the focused test and the existing config suite.

## Task 2: Define truthful M0 readiness contracts

**Files:**

- Create: `src/omra/monitoring/readiness.py`
- Create: `tests/unit/monitoring/test_readiness.py`

1. Write failing tests for an immutable, JSON-safe readiness report with stable checks:
   `config`, `database`, `schema`, and `volumes`.
2. Require overall `ready` only when every check passes; failures must contain bounded diagnostic
   codes without secrets or tracebacks.
3. Test SQLite connectivity and Alembic revision without mutating an initialized database.
4. Test required writable directories with a create/fsync/remove probe and verify cleanup on both
   success and failure.
5. Implement only local file/SQLite checks; no broker, DNS, HTTP, or object-storage call is allowed.

## Task 3: Implement the fail-closed M0 bootstrap

**Files:**

- Create: `src/omra/runtime/bootstrap.py`
- Create: `tests/unit/runtime/test_bootstrap.py`

1. Write failing tests for path creation, empty-database initialization, Alembic-head verification,
   KILL refusal, existing non-head database refusal, and cleanup of process-local persistence.
2. Build Alembic configuration from repository/package paths rather than shelling out.
3. Permit automatic migration only when the target SQLite file is absent or structurally empty.
   Never upgrade an existing initialized database in this M0 path.
4. Load and validate configuration with `SystemClock`, initialize the writer once, and return an
   immutable runtime context consumed by readiness/web composition.
5. Keep scheduler, broker, bot-state transitions, watchdog, and worker tasks out of this module.

## Task 4: Expose `/readyz`, `omra run`, and `omra ready`

**Files:**

- Create: `src/omra/web/app.py`
- Create: `src/omra/cli/runtime.py`
- Modify: `src/omra/cli/__init__.py`
- Create: `tests/unit/web/test_app.py`
- Create: `tests/unit/cli/test_runtime.py`

1. Write failing route tests: ready report returns 200, failed report returns 503, response validates
   against the readiness schema, and no final `/healthz` route is silently introduced.
2. Write failing CLI tests: `ready` exits 0 only for a valid 200/ready response; connection errors,
   timeouts, malformed payloads, non-200 responses, and report failures exit 1 with bounded output.
3. Implement an injected FastAPI app factory so `web` never imports `runtime`.
4. Implement `run` as the composition root around bootstrap + Uvicorn and guarantee persistence
   disposal on normal exit and startup failure.
5. Keep host, port, config path, database path, and volume paths explicit/testable while retaining
   safe container defaults.

## Task 5: Add reproducible least-privileged containers

**Files:**

- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `compose.yaml`
- Create: `compose.smoke.yaml`
- Create: `config/litestream.yml`
- Create: `config/litestream.smoke.yml`
- Create: `.env.example`
- Create: `.env.litestream.example`
- Create: `.env.tools.example`
- Modify: `.gitignore`
- Create: `tests/arch/test_container_contract.py`

1. Write failing architecture tests that parse Dockerfile/Compose/Litestream/environment examples
   and assert exact service set, tools profile, non-root/read-only/tmpfs boundaries, volume and
   credential separation, health command, log rotation, stop grace, and singular v0.5 `replica`.
2. Resolve current official Python, uv, and Litestream image tags and multi-architecture manifest
   digests. Pin immutable digests; do not use `latest` or an architecture-specific digest as a
   multi-architecture reference.
3. Build a multi-stage image with a locked, non-editable production environment and no build tools
   in the runtime stage. Run as UID/GID 1000 and write only to declared volumes/tmpfs.
4. Make `app` the sole DB writer, `litestream` share only DB/config, and `tools` omit DB and broker
   credentials. Whitelist only `*.example` env templates in Git.
5. Use the production S3 replica contract in `config/litestream.yml`; use a local file replica only
   in the smoke override.
6. Run static architecture tests before attempting any container execution.

## Task 6: Add deterministic remote container smoke evidence

**Files:**

- Create: `scripts/container_smoke.sh`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/arch/test_ci_security.py`

1. Write failing CI/static tests requiring a bounded `container-smoke` job, read-only repository
   permissions, no GitHub secrets, pinned actions, and a timeout.
2. Implement a POSIX shell smoke script with explicit project name and cleanup trap. It must build,
   start app + Litestream with the file-replica override, wait for healthy, create a deterministic DB
   write, observe a replica generation, restore into a new target, and run SQLite integrity checks.
3. Add the GitHub-hosted runner job. Keep it supplemental: it proves the deterministic container
   contract but does not claim the credentialed M0 operational gate.
4. Push only after all local non-container gates pass; use PR CI output as the fresh Docker evidence.

## Task 7: Synchronize canonical documentation

**Files:**

- Modify: `docs/plan/01-architecture.md`
- Modify: `docs/design/01-system-architecture.md`
- Modify: `docs/design/03-data-and-persistence.md`
- Modify: `docs/design/12-scheduling-and-operations.md`
- Modify: `docs/design/16-testing-and-quality.md`
- Modify: `CONTRIBUTING.md` only if the automatic relay policy needs repository-level clarification

1. Replace legacy Litestream `replicas:` examples with the verified v0.5 singular `replica:` form.
2. Record immutable image pinning and sidecar shutdown behavior.
3. Separate M0 `/readyz` from the final M3 `/healthz` contract; make the incremental boundary and
   removal criteria explicit.
4. Clarify that container CI is reproducible implementation evidence while real S3/restore and KIS
   evidence remain manual operational gates.
5. Do not resolve VACUUM snapshot confirmation or restore flags beyond what official v0.5 docs and
   the implemented smoke test prove.

## Task 8: Verify, review, and deliver issue #46

1. Run focused tests after every task, then fresh full gates:
   `ruff check .`, `ruff format --check .`, `mypy`, `lint-imports`, `pytest -q`,
   `pip-audit --skip-editable`, and `uv lock --check` where the tool exists.
2. Inspect `git diff --check`, staged diff, file modes, binary additions, and secret-like content.
3. Request an independent code review, fix all high/medium findings, and repeat affected gates.
4. Commit with the configured identity and a Korean Conventional Commit including a `Tests:` field.
5. Push `feat/m0-container-runtime`, open a PR linked to #46, and wait for all required checks.
6. Merge only after remote container smoke and normal CI are green. Close #46, set Project #3 to
   `Done`, and add a detailed next-session relay comment naming exactly one next Kanban candidate.
7. Do not start that next card in this conversation.
