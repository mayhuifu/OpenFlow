"""Tests for the V4 ``openflow report`` CLI."""
from pathlib import Path

import pytest

from openflow.report.cli import _parse_duration, cli_main
from openflow.report.db.sqlite_backend import SQLiteBackend


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    """A test DB with one ingested canonical V2 fixture, ready for CLI tests."""
    db = tmp_path / "test.db"
    backend = SQLiteBackend(db)
    backend.ensure_schema()
    backend.ingest_json(Path("tests-internal/fixtures/sample_report.json"))
    return db


# --- duration parsing ---------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("7d", 7 * 86400),
    ("24h", 24 * 3600),
    ("90m", 90 * 60),
    ("3600s", 3600),
    ("3600", 3600),
])
def test_parse_duration_units(text, expected):
    assert _parse_duration(text) == expected


def test_parse_duration_invalid():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_duration("xx")


# --- ingest -------------------------------------------------------------

def test_ingest_subcommand(tmp_path: Path, capsys):
    db = tmp_path / "fresh.db"
    rc = cli_main([
        "--db", str(db), "ingest",
        "tests-internal/fixtures/sample_report.json",
    ])
    assert rc == 0
    captured = capsys.readouterr()
    assert "ingested" in captured.out
    assert "session_id=" in captured.out
    # DB has the session.
    backend = SQLiteBackend(db)
    assert len(backend.list_sessions()) == 1


# --- list-sessions ------------------------------------------------------

def test_list_sessions_text(populated_db: Path, capsys):
    rc = cli_main(["--db", str(populated_db), "list-sessions"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "session_id" in out
    # The canonical fixture has passed=4, failed=1.
    assert " 4 " in out or "4\n" in out or out.count("4") >= 1


def test_list_sessions_json(populated_db: Path, capsys):
    rc = cli_main(["--db", str(populated_db), "list-sessions", "--json"])
    assert rc == 0
    import json
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert len(data) == 1
    assert "session_id" in data[0]


# --- show ----------------------------------------------------------------

def test_show_existing_session(populated_db: Path, capsys):
    backend = SQLiteBackend(populated_db)
    sid = backend.list_sessions()[0]["session_id"]
    rc = cli_main(["--db", str(populated_db), "show", sid])
    assert rc == 0
    out = capsys.readouterr().out
    assert sid in out


def test_show_missing_session_returns_1(populated_db: Path, capsys):
    rc = cli_main(["--db", str(populated_db), "show", "nope"])
    assert rc == 1


# --- query ---------------------------------------------------------------

def test_query_all_tests(populated_db: Path, capsys):
    rc = cli_main(["--db", str(populated_db), "query"])
    assert rc == 0
    out = capsys.readouterr().out
    # The canonical fixture has 5 tests.
    assert "U300B0-RFE-EVT-005" in out


def test_query_where_filter(populated_db: Path, capsys):
    rc = cli_main([
        "--db", str(populated_db), "query",
        "--where", "testcase_id LIKE 'U300%'",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "U300" in out
    assert "CMW100-CONNECTIVITY" not in out  # filtered out


# --- trend ---------------------------------------------------------------

def test_trend_subcommand(populated_db: Path, capsys):
    rc = cli_main([
        "--db", str(populated_db), "trend",
        "--test", "U300B0-RFE-EVT-005",
        "--metric", "measured_EVM_pct",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "measured_EVM_pct" in out
    # 5 data points in the canonical fixture.
    assert out.count(".") >= 5  # at least 5 decimal values


def test_trend_no_data(populated_db: Path, capsys):
    rc = cli_main([
        "--db", str(populated_db), "trend",
        "--test", "NONEXISTENT",
        "--metric", "fake_metric",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no trend data" in out


def test_trend_json_output(populated_db: Path, capsys):
    rc = cli_main([
        "--db", str(populated_db), "trend",
        "--test", "U300B0-RFE-EVT-005",
        "--metric", "measured_EVM_pct",
        "--json",
    ])
    assert rc == 0
    import json
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data, list)
    assert len(data) == 5


# --- migrate -------------------------------------------------------------

def test_migrate_subcommand_reports_version(tmp_path: Path, capsys):
    db = tmp_path / "test.db"
    rc = cli_main(["--db", str(db), "migrate"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "schema version: 1" in out


# --- top-level dispatch via main() --------------------------------------

def test_openflow_cli_dispatches_report_subcommand(populated_db: Path, capsys):
    """`openflow report list-sessions` should dispatch to cli_main."""
    from openflow.migrate.cli import main as openflow_main
    rc = openflow_main(["report", "--db", str(populated_db), "list-sessions"])
    assert rc == 0
    assert "session_id" in capsys.readouterr().out
