# OpenFlow — V4 Design (Persistent Results)

**Status:** Vision-level draft (plan deferred until V3 ships)
**Date:** 2026-05-22
**Supersedes / extends:** [`2026-05-22-openflow-v1-design.md`](./2026-05-22-openflow-v1-design.md), [`2026-05-22-openflow-v2-design.md`](./2026-05-22-openflow-v2-design.md), [`2026-05-22-openflow-v3-design.md`](./2026-05-22-openflow-v3-design.md)
**Audience:** RF engineering team + framework maintainers

> **Why vision-level:** V4 is two-to-three milestones away. Locking implementation details now would be premature speculation — the V2 bulk-migration + V3 instrument coverage will sharpen V4's scope. This spec captures **what** V4 ships and **why**, with implementation details deliberately left soft. A full executable plan lands once V3 ships and the data shape stabilizes.

---

## 1. What is V4?

V4 makes test results **persistent and queryable**. Today every test session
emits a single `report.json` (V1) and `report.html` (V2). Those files are
the artifacts an engineer sends in a Slack message or attaches to a Jira
ticket. They're not designed to answer questions like:

- "Did this regression appear after the firmware update last Friday?"
- "What's the RX gain delta trend on board #131694 over the last 30 days?"
- "How often does the TX EVM at -10 dBm exceed 2.5% across the whole U300 fleet?"

V4 introduces a **local-default, optionally-shared** results database that
turns each `report.json` into a query-able historical record:

- **Default backend: SQLite.** Zero configuration — the database file
  lives next to the test report (`report.db` alongside `report.json`).
  Engineer runs `openflow report query ...` against it from the CLI.
- **Optional backend: PostgreSQL.** Multi-bench, shared. The engineer
  sets a connection string in YAML; the framework writes every test
  result to the shared DB on top of the local one. Enables team-wide
  trend analysis without each engineer hand-uploading their JSONs.
- **Schema versioned + migratable.** Adding a new measurement type
  doesn't require a database rebuild; the framework runs migrations on
  open.

V4 does **not** add a web UI — that's V5. V4's surface is a CLI
(`openflow report query`, `openflow report ingest`, `openflow report
trend`) plus a Python API (`from openflow.report.db import ReportDB`).

---

## 2. V4 scope

### Why this lands in v4 (not earlier or later)

- **After V2 + V3.** V2 finalizes the per-test JSON schema (HTML renderer
  fixes it in place); V3 ensures the instrument surface is stable. V4
  builds on that stable surface — locking the database schema before
  V3's measurement diversity would invite premature versioning.
- **Before V5.** The web dashboard (V5) reads from V4's database. Trying
  to build the dashboard against per-session JSON files would force a
  weak read API; building it against V4 gives a real query layer.

### Success criteria

V4 is "shipped" when **all** of the following hold:

1. **Local SQLite mode works automatically.** Running any test produces a
   `report.db` next to `report.json` with the same data, queryable via
   the CLI:

   ```sh
   uv run openflow report query --where 'test_id LIKE "%TX_EVM%"' --since 7d
   ```

   …prints a table of matching tests with their verdicts and key
   measurements.

2. **Optional PostgreSQL ingest works.** With a `[storage] postgres_dsn`
   line in `openflow.yaml`, every test session also writes to the shared
   DB. Failure to reach the shared DB is a warning, not a test failure —
   local SQLite stays the source of truth.

3. **Schema migration mechanism in place.** Adding a column (e.g. a new
   measurement type) is a single migration file. Existing test results
   remain queryable; new tests use the new schema. CI runs a migration
   round-trip test.

4. **Trend analysis CLI works.** `openflow report trend --metric
   out_EVM_pct --test U300B0-RFE-EVT-005 --days 30` prints (or
   optionally plots) the metric's value over time.

5. **JSON migration tool ships.** Engineers with archived
   `report.json` files from V1-V3 can ingest them into the database:
   `openflow report ingest path/to/old_report.json`.

6. **CI green.** ≥350 internal tests passing. Database operations covered by
   unit tests (against an in-memory SQLite) and integration tests
   (against a containerized PostgreSQL).

### Explicit non-goals for V4

- Web dashboard (V5)
- Real-time streaming of in-progress test results (V5+)
- Multi-DUT cross-correlation queries (V5)
- ML / anomaly detection on the trend data (out of scope indefinitely;
  the engineer's eye is the detector for v1-v5)
- Replacing JSON / HTML as the primary deliverable (those stay)

---

## 3. Architecture (sketch — to be sharpened in the plan)

### Module layout

```
openflow/
├── report/
│   ├── html.py                  # existing from V2
│   ├── db/                      # NEW V4
│   │   ├── __init__.py
│   │   ├── schema.py            # SQLAlchemy models OR sqlite3-direct schema
│   │   ├── migrations/          # versioned migration scripts
│   │   ├── sqlite_backend.py
│   │   ├── postgres_backend.py
│   │   └── queries.py           # high-level query helpers
│   └── cli.py                   # NEW V4 — `openflow report ...` subcommands
└── ...
```

### Database schema (rough)

The schema mirrors the JSON report's structure — sessions contain tests,
tests contain parametrize cases, parametrize cases contain measurements:

```
sessions       (session_id, started_at, finished_at, host, openflow_version, config_path)
tests          (test_id, session_id, test_node_id, testcase_id, verdict, duration_s)
cases          (case_id, test_id, params)            -- params is JSON
measurements   (measurement_id, case_id, name, value, unit)
```

Indexes on (testcase_id, started_at) for trend queries, on (session_id)
for per-session lookups.

### Backend choice

- **SQLite** (default): zero-deps, on-disk file, suitable for single-bench
  use. Native in CPython, no install step.
- **PostgreSQL** (optional): proper concurrent writes, network-accessible,
  suitable for shared lab DB. Requires `psycopg2-binary` (declared as an
  optional extra in pyproject — `uv sync --extra postgres` installs it).

ORM vs raw: prefer SQLAlchemy Core (not ORM) for the schema — keeps the
queries SQL-readable, avoids ORM-overhead, and makes the migration story
explicit. ORM patterns aren't needed at the scale we're targeting
(< 1M rows per bench / year).

### CLI surface

```sh
openflow report ingest <file.json>       # one-shot load from V1-V3 JSON
openflow report query --where '...' --since 7d
openflow report trend --metric <name> --test <id> [--plot]
openflow report list-sessions
openflow report show <session-id>
openflow report migrate                  # run pending schema migrations
```

Output formats:
- Default: human-readable table (rich)
- `--json`: machine-parsable JSON for piping into other tools
- `--csv`: spreadsheet-friendly

### Concurrency model

- SQLite: single-writer, multi-reader. Test sessions write
  serially via WAL mode. A long-running query while a test is publishing
  results is safe.
- PostgreSQL: connection pool of 4 (configurable). Each test session
  opens one connection at session start and closes at session end.

### Migrations

A simple file-based migration approach (no Alembic / Django dependency):

```
openflow/report/db/migrations/
├── 0001_initial.sql
├── 0002_add_unit_column.sql
└── ...
```

The framework records the highest-applied migration in a
`schema_version` table. `openflow report migrate` runs unapplied
migrations in order. SQLite + PostgreSQL share the schema SQL where
syntax allows; vendor-specific quirks live in per-backend overrides.

---

## 4. Phase split (proposed; finalize after V3)

### V4a — SQLite default (unblocked)

- Schema design + initial migration
- `sqlite_backend.py` write path (called from `pytest_sessionfinish`)
- `openflow report ingest|query|list-sessions|show` CLI
- Tests: unit (in-memory SQLite) + canonical-fixture round-trip
- Documentation: schema diagram, CLI examples

**Definition of done:** Running any test produces a queryable `report.db`;
all V1-V3 archived JSONs can be ingested.

### V4b — PostgreSQL backend (unblocked by V4a)

- `postgres_backend.py`
- Optional dep declared
- Failure-tolerant: shared DB unreachable doesn't fail tests
- CI integration test using a Postgres container

**Definition of done:** Tests can write to both backends simultaneously;
shared DB outage doesn't impact local operation.

### V4c — Trend analysis (unblocked by V4a)

- `openflow report trend` CLI
- Optional plot output (matplotlib — declared as optional dep)
- 1-2 worked examples in `docs/v4-trend-analysis-guide.md`

**Definition of done:** Engineer can produce a 30-day metric trend in
< 5 seconds against a populated SQLite.

Sequencing: V4a → V4b in parallel with V4c → release.

---

## 5. Risks and unknowns

### Risk: schema lock-in is hard to undo

A schema mistake in V4 leaves every test session's data with a clunky
shape. Migrations are possible but expensive once data accumulates.

**Mitigation:** Beta period. V4a ships behind a feature flag
(`storage.persist: false` by default) for one release; engineers
exercise it on real test data; schema feedback applied; flag flipped
on by default for the v4 release. This adds two milestones but
materially reduces schema-mistake risk.

### Risk: PostgreSQL setup overhead

Setting up a shared Postgres for a team of 4 engineers is a non-trivial
sysadmin task (DNS, auth, backups, schema sync). If the team doesn't
have an existing internal Postgres they can use, V4b's value is low.

**Mitigation:** Document an embedded-server alternative
(SQLite-over-NFS, or a single-engineer-runs-the-server pattern) for
small teams. Postgres is the "real" multi-bench answer but not the only
one.

### Risk: Engineers prefer the JSON

If the JSON is what they paste into tickets, and the HTML is what they
email, the database may end up unused. We'd ship infrastructure no one
queries.

**Mitigation:** Make the CLI value obvious. The trend command in
particular should produce an answer that the JSON-via-ticket workflow
cannot — "show me this metric over the last 30 days" is the V4 pitch.

### Risk: ingest of older JSONs has bad shape

The V1 JSON format may evolve subtly across v0.2.0-v0.4.0; old archives
may not ingest cleanly.

**Mitigation:** The ingest tool warns + skips records it can't parse,
rather than failing. Engineer can fix records by hand if needed.

---

## 6. Open questions for engineering review (to revisit when V3 ships)

1. **PostgreSQL or DuckDB?** DuckDB is a no-server columnar embedded DB
   that handles analytics workloads better than SQLite and doesn't
   require server setup. Worth considering as the optional backend
   instead of (or alongside) PostgreSQL.

2. **Where does the DB live in CI?** The CI's per-job filesystem is
   ephemeral — `report.db` is recreated each run. That's fine for testing
   the write path, but trend analysis needs persistence. Question: do we
   expect CI to also push to the shared DB, or is V4 explicitly
   bench-only?

3. **PII / proprietary measurements.** If measurements include device
   serial numbers and the DB is shared, downstream queries could expose
   proprietary info. Need a redaction option or a per-team "private
   measurements" mode.

4. **Migration tool for historical archives.** Worth investing in, or
   start fresh? Recommendation: invest. Engineers have years of test
   data they want trended.

5. **CLI vs in-test API.** Does the engineer also want
   `results.publish_to_db(...)` callable from within a test, or only via
   the post-session hook? Recommendation: post-session only —
   test-during-write coupling is what V1 deliberately avoided.

---

## 7. Out of band: roadmap relative position

V4 follows V3 (instrument coverage) and precedes V5 (lab orchestration).
V4 is **the data layer V5's dashboard reads from**, so V5 depends on V4
landing first.

The natural release sequencing:

- v0.5.0 (V2a — bulk migration + HTML)
- v0.6.0 (V2b — bench validation of 2 migrated tests)
- v0.7.0 (V3a — SG/SA/WFG drivers)
- v0.8.0 (V3b — bench validation of 4 instrument bring-ups)
- v0.9.0 (V4a — SQLite + CLI)
- v0.10.0 (V4b — PostgreSQL + V4c trend analysis)
- v1.0.0 (V5)

After V4: [V5 — Lab orchestration](./2026-05-22-openflow-v5-design.md).
