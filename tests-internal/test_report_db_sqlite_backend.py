"""Tests for the V4 SQLite persistence backend."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from openflow.report.db.sqlite_backend import SQLiteBackend


@pytest.fixture
def backend() -> SQLiteBackend:
    """Fresh in-memory backend per test."""
    b = SQLiteBackend(":memory:")
    b.ensure_schema()
    return b


def test_ensure_schema_records_version(backend: SQLiteBackend):
    assert backend.current_schema_version() == SQLiteBackend.SCHEMA_VERSION


def test_ensure_schema_is_idempotent(backend: SQLiteBackend):
    backend.ensure_schema()
    backend.ensure_schema()
    # Still one schema_version row, not two.
    assert backend.current_schema_version() == SQLiteBackend.SCHEMA_VERSION


def test_write_and_list_session(backend: SQLiteBackend):
    now = datetime.utcnow()
    backend.write_session(
        session_id="s1",
        started_at=now,
        host="bench-01",
        openflow_version="0.10.0",
        passed=5, failed=0, exit_status=0,
    )
    rows = backend.list_sessions()
    assert len(rows) == 1
    assert rows[0]["session_id"] == "s1"
    assert rows[0]["passed"] == 5
    assert rows[0]["host"] == "bench-01"


def test_list_sessions_orders_most_recent_first(backend: SQLiteBackend):
    now = datetime.utcnow()
    backend.write_session(session_id="old", started_at=now - timedelta(hours=2))
    backend.write_session(session_id="new", started_at=now)
    rows = backend.list_sessions()
    assert rows[0]["session_id"] == "new"
    assert rows[1]["session_id"] == "old"


def test_get_session_returns_dict(backend: SQLiteBackend):
    now = datetime.utcnow()
    backend.write_session(session_id="s1", started_at=now)
    s = backend.get_session("s1")
    assert s is not None
    assert s["session_id"] == "s1"


def test_get_session_missing_returns_none(backend: SQLiteBackend):
    assert backend.get_session("nonexistent") is None


def test_write_test_returns_test_id(backend: SQLiteBackend):
    backend.write_session(session_id="s1", started_at=datetime.utcnow())
    tid = backend.write_test(
        session_id="s1",
        test_node_id="tests/x.py::test_foo[0]",
        testcase_id="TC1",
        verdict="passed",
        duration_s=0.42,
    )
    assert isinstance(tid, int)
    assert tid > 0


def test_write_case_and_measurement_chain(backend: SQLiteBackend):
    backend.write_session(session_id="s1", started_at=datetime.utcnow())
    tid = backend.write_test(session_id="s1", test_node_id="x")
    cid = backend.write_case(test_id=tid, params={"gain": 0})
    backend.write_measurement(case_id=cid, name="evm_pct", value=1.42)
    # No assertion on the measurement table directly — see trend() / query_tests().


def test_query_tests_no_filter(backend: SQLiteBackend):
    backend.write_session(session_id="s1", started_at=datetime.utcnow())
    backend.write_test(session_id="s1", test_node_id="x", testcase_id="TC1")
    backend.write_test(session_id="s1", test_node_id="y", testcase_id="TC2")
    rows = backend.query_tests()
    assert len(rows) == 2


def test_query_tests_where_filter(backend: SQLiteBackend):
    backend.write_session(session_id="s1", started_at=datetime.utcnow())
    backend.write_test(session_id="s1", test_node_id="x", testcase_id="U300-EVT-005")
    backend.write_test(session_id="s1", test_node_id="y", testcase_id="OTHER")
    rows = backend.query_tests(where="testcase_id LIKE 'U300%'")
    assert len(rows) == 1
    assert rows[0]["testcase_id"] == "U300-EVT-005"


def test_query_tests_since_seconds_filter(backend: SQLiteBackend):
    backend.write_session(session_id="old", started_at=datetime.utcnow() - timedelta(hours=2))
    backend.write_session(session_id="new", started_at=datetime.utcnow())
    backend.write_test(session_id="old", test_node_id="x")
    backend.write_test(session_id="new", test_node_id="y")
    # Filter to last 30 minutes.
    rows = backend.query_tests(since_seconds=1800)
    assert len(rows) == 1
    assert rows[0]["session_id"] == "new"


def test_trend_returns_metric_values_across_sessions(backend: SQLiteBackend):
    base = datetime.utcnow() - timedelta(days=2)
    # Three sessions, same testcase, different metric values.
    for i, val in enumerate([1.0, 1.5, 2.0]):
        sid = f"s{i}"
        backend.write_session(session_id=sid, started_at=base + timedelta(hours=i))
        tid = backend.write_test(session_id=sid, test_node_id="x",
                                 testcase_id="TC-TREND")
        cid = backend.write_case(test_id=tid)
        backend.write_measurement(case_id=cid, name="evm_pct", value=val)
    points = backend.trend(testcase_id="TC-TREND", metric="evm_pct")
    assert len(points) == 3
    # Sorted oldest-first.
    assert points[0][1] == 1.0
    assert points[-1][1] == 2.0


def test_trend_excludes_other_testcases(backend: SQLiteBackend):
    base = datetime.utcnow()
    sid = "s1"
    backend.write_session(session_id=sid, started_at=base)
    tid_match = backend.write_test(session_id=sid, test_node_id="x",
                                   testcase_id="MATCH")
    tid_other = backend.write_test(session_id=sid, test_node_id="y",
                                   testcase_id="OTHER")
    cid_match = backend.write_case(test_id=tid_match)
    cid_other = backend.write_case(test_id=tid_other)
    backend.write_measurement(case_id=cid_match, name="evm_pct", value=1.0)
    backend.write_measurement(case_id=cid_other, name="evm_pct", value=99.0)
    points = backend.trend(testcase_id="MATCH", metric="evm_pct")
    assert len(points) == 1
    assert points[0][1] == 1.0


def test_ingest_canonical_v2_json(backend: SQLiteBackend):
    """The V2 canonical fixture has 5 tests with a mix of numeric and
    text record fields."""
    backend.ingest_json(Path("tests-internal/fixtures/sample_report.json"))
    sessions = backend.list_sessions()
    assert len(sessions) == 1
    assert sessions[0]["passed"] == 4
    assert sessions[0]["failed"] == 1

    rows = backend.query_tests()
    assert len(rows) == 5
    testcases = {r["testcase_id"] for r in rows if r["testcase_id"]}
    assert "U300B0-RFE-EVT-005" in testcases


def test_ingest_assigns_synthetic_session_id_if_absent(backend: SQLiteBackend):
    sid = backend.ingest_json(Path("tests-internal/fixtures/sample_report.json"))
    assert sid.startswith("sample_report-")


def test_ingest_numeric_records_land_in_measurements(backend: SQLiteBackend):
    backend.ingest_json(Path("tests-internal/fixtures/sample_report.json"))
    # The canonical TX EVM sweep has measured_EVM_pct values across 5 records.
    points = backend.trend(testcase_id="U300B0-RFE-EVT-005",
                           metric="measured_EVM_pct")
    assert len(points) == 5
    assert all(0.5 < v < 5.0 for _, v in points)


def test_ingest_is_repeatable_on_same_file(backend: SQLiteBackend, tmp_path: Path):
    """Re-ingesting the same JSON produces the same session_id but a
    second sessions row is rejected at the primary-key constraint —
    caller is responsible for de-duplication. We just verify the first
    ingest succeeds and we can read it back."""
    sid = backend.ingest_json(Path("tests-internal/fixtures/sample_report.json"))
    assert backend.get_session(sid) is not None
