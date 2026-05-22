"""SQLAlchemy Core schema for V4 persistent results.

We use SQLAlchemy Core (Tables + Columns, no ORM mapping) so:

- Queries stay SQL-readable (engineers can debug with sqlite3 / psql
  directly).
- There's no ORM-overhead at the ~1M-rows-per-bench-per-year scale we
  target.
- Same schema works against SQLite (development / local default) and
  PostgreSQL (shared multi-bench) without backend-specific overrides.

The schema has four core tables:

    sessions      — one row per pytest session
    tests         — one row per test function within a session
    cases         — one row per parametrize iteration within a test
    measurements  — one row per `results.publish(key=value)` argument

Plus a ``schema_version`` table used by the file-based migration runner
in ``sqlite_backend.py``.

For trend queries (``openflow report trend --metric ...``), the
``measurements`` table is wide enough to support the common case
without join-heavy SQL: filter by ``name``, group by ``cases.test_id``,
join on ``sessions.started_at``.
"""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
)

metadata = MetaData()

# One row per pytest session (one `pytest` invocation).
sessions = Table(
    "sessions", metadata,
    Column("session_id", String, primary_key=True),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime, nullable=True),
    Column("host", String, nullable=True),
    Column("openflow_version", String, nullable=True),
    Column("config_path", String, nullable=True),
    Column("passed", Integer, nullable=True),
    Column("failed", Integer, nullable=True),
    Column("exit_status", Integer, nullable=True),
)

# One row per test function within a session.
tests = Table(
    "tests", metadata,
    Column("test_id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String,
           ForeignKey("sessions.session_id", ondelete="CASCADE"),
           nullable=False),
    Column("test_node_id", String, nullable=False),
    Column("testcase_id", String, nullable=True),
    Column("verdict", String, nullable=True),
    Column("duration_s", Float, nullable=True),
)

# One row per parametrize iteration (or single record-emit if not parametrized).
cases = Table(
    "cases", metadata,
    Column("case_id", Integer, primary_key=True, autoincrement=True),
    Column("test_id", Integer,
           ForeignKey("tests.test_id", ondelete="CASCADE"),
           nullable=False),
    Column("params", JSON, nullable=True),
    Column("recorded_at", DateTime, nullable=True),
)

# One row per `results.publish(key=value)` argument.
# Numeric values land in ``value``; non-numeric (e.g. IDN strings) in ``text_value``.
measurements = Table(
    "measurements", metadata,
    Column("measurement_id", Integer, primary_key=True, autoincrement=True),
    Column("case_id", Integer,
           ForeignKey("cases.case_id", ondelete="CASCADE"),
           nullable=False),
    Column("name", String, nullable=False),
    Column("value", Float, nullable=True),
    Column("text_value", String, nullable=True),
    Column("unit", String, nullable=True),
)

# Indexes for the common query patterns:
#   - "trend a metric over time"   → measurements(name) + sessions(started_at)
#   - "all sessions"               → sessions(started_at)
#   - "tests for a testcase"       → tests(testcase_id)
Index("idx_sessions_started_at", sessions.c.started_at)
Index("idx_tests_testcase_id", tests.c.testcase_id)
Index("idx_tests_session_id", tests.c.session_id)
Index("idx_measurements_name", measurements.c.name)
Index("idx_measurements_case_id", measurements.c.case_id)

# Schema version tracking — used by sqlite_backend.run_migrations().
schema_version = Table(
    "schema_version", metadata,
    Column("version", Integer, primary_key=True),
    Column("applied_at", DateTime, nullable=False),
)


# Public list of all tables for the schema-create / drop_all flow.
ALL_TABLES = [sessions, tests, cases, measurements, schema_version]
