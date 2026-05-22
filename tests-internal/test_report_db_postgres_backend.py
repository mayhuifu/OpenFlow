"""Tests for the V4 PostgreSQL persistence backend.

These tests are **gated on the ``OPENFLOW_TEST_PG_DSN`` env var** — if
not set, they all skip cleanly. Set up a local Postgres + DSN to run:

    docker run --rm -d --name openflow-pg -e POSTGRES_PASSWORD=test \\
        -p 5432:5432 postgres:16
    export OPENFLOW_TEST_PG_DSN="postgresql+psycopg2://postgres:test@localhost:5432/postgres"
    uv run pytest tests-internal/test_report_db_postgres_backend.py
"""
import os
from datetime import datetime

import pytest

PG_DSN = os.environ.get("OPENFLOW_TEST_PG_DSN")


pytestmark = pytest.mark.skipif(
    not PG_DSN,
    reason="OPENFLOW_TEST_PG_DSN env var not set — Postgres tests skipped",
)


@pytest.fixture
def pg_backend():
    """A fresh PostgreSQL backend — schema dropped before and after."""
    from openflow.report.db.postgres_backend import PostgreSQLBackend
    from openflow.report.db.schema import metadata

    backend = PostgreSQLBackend(PG_DSN)
    # Clean slate.
    metadata.drop_all(backend._engine)
    backend.ensure_schema()
    yield backend
    metadata.drop_all(backend._engine)


def test_postgres_write_and_list_session(pg_backend):
    pg_backend.write_session(
        session_id="pg-s1",
        started_at=datetime.utcnow(),
        host="bench-01",
        passed=5, failed=0, exit_status=0,
    )
    sessions = pg_backend.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "pg-s1"


def test_postgres_trend_query(pg_backend):
    from datetime import timedelta
    base = datetime.utcnow() - timedelta(days=1)
    for i, val in enumerate([1.0, 1.5, 2.0]):
        sid = f"pg-s{i}"
        pg_backend.write_session(session_id=sid, started_at=base + timedelta(hours=i))
        tid = pg_backend.write_test(session_id=sid, test_node_id="x",
                                    testcase_id="PG-TREND")
        cid = pg_backend.write_case(test_id=tid)
        pg_backend.write_measurement(case_id=cid, name="evm_pct", value=val)
    points = pg_backend.trend(testcase_id="PG-TREND", metric="evm_pct")
    assert len(points) == 3
    assert [v for _, v in points] == [1.0, 1.5, 2.0]


def test_postgres_ingest_canonical_json(pg_backend):
    from pathlib import Path
    pg_backend.ingest_json(Path("tests-internal/fixtures/sample_report.json"))
    sessions = pg_backend.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["passed"] == 4
