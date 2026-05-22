"""Tests for the V5c read-only FastAPI dashboard."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openflow.bench.reservation import LocalReservationStore
from openflow.dashboard.server import create_app
from openflow.report.db.sqlite_backend import SQLiteBackend


@pytest.fixture
def populated_setup(tmp_path: Path) -> tuple[Path, Path]:
    """A V4 DB + V5a reservations file, both populated for dashboard tests."""
    db = tmp_path / "test.db"
    backend = SQLiteBackend(db)
    backend.ensure_schema()
    backend.ingest_json(Path("tests-internal/fixtures/sample_report.json"))

    reservations = tmp_path / "reservations.json"
    store = LocalReservationStore(reservations)
    store.reserve("TCPIP::cmw1::INSTR", by="alice",
                  duration_s=3600, reason="TX EVM baseline")

    return db, reservations


@pytest.fixture
def client(populated_setup: tuple[Path, Path]) -> TestClient:
    db, reservations = populated_setup
    app = create_app(db_path=db, reservations_path=reservations)
    return TestClient(app)


def test_home_returns_html(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "OpenFlow dashboard" in r.text


def test_home_lists_recent_sessions(client: TestClient):
    r = client.get("/")
    assert "session" in r.text.lower()
    # The canonical V2 fixture has one session — its synthetic ID
    # contains "sample_report-".
    assert "sample_report" in r.text


def test_sessions_list_returns_html(client: TestClient):
    r = client.get("/sessions")
    assert r.status_code == 200
    assert "All sessions" in r.text


def test_session_detail_for_existing(client: TestClient):
    # Fetch the session ID from the populated DB.
    sessions_response = client.get("/api/sessions")
    assert sessions_response.status_code == 200
    sid = sessions_response.json()[0]["session_id"]

    r = client.get(f"/sessions/{sid}")
    assert r.status_code == 200
    assert sid in r.text
    # Tests table is rendered.
    assert "U300B0-RFE-EVT-005" in r.text


def test_session_detail_missing_returns_404(client: TestClient):
    r = client.get("/sessions/nonexistent")
    assert r.status_code == 404


def test_bench_endpoint_shows_reservation(client: TestClient):
    r = client.get("/bench")
    assert r.status_code == 200
    assert "alice" in r.text
    assert "TCPIP::cmw1::INSTR" in r.text
    assert "TX EVM baseline" in r.text


def test_trends_form_renders_without_query(client: TestClient):
    r = client.get("/trends")
    assert r.status_code == 200
    assert "<form" in r.text


def test_trends_with_query_renders_chart(client: TestClient):
    r = client.get("/trends", params={
        "test": "U300B0-RFE-EVT-005",
        "metric": "measured_EVM_pct",
    })
    assert r.status_code == 200
    # The canonical fixture has 5 data points → SVG chart should appear.
    assert "<svg" in r.text or "data point" in r.text or "identical" in r.text


# --- JSON API endpoints --------------------------------------------------

def test_api_sessions_returns_json(client: TestClient):
    r = client.get("/api/sessions")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert "session_id" in data[0]


def test_api_session_tests_returns_json(client: TestClient):
    sid = client.get("/api/sessions").json()[0]["session_id"]
    r = client.get(f"/api/sessions/{sid}/tests")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 5  # canonical fixture has 5 tests


def test_api_session_tests_missing_returns_404(client: TestClient):
    r = client.get("/api/sessions/nonexistent/tests")
    assert r.status_code == 404


def test_api_bench_returns_json(client: TestClient):
    r = client.get("/api/bench")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["acquired_by"] == "alice"


def test_no_write_endpoints(client: TestClient):
    """V5c constraint: dashboard is read-only. POST/PUT/DELETE should
    not be available on any of our endpoints."""
    for method in ("post", "put", "delete", "patch"):
        for path in ("/sessions/x", "/bench", "/trends"):
            r = getattr(client, method)(path)
            # FastAPI returns 405 Method Not Allowed for unsupported verbs.
            assert r.status_code == 405


def test_dashboard_cli_dispatches_via_top_level_openflow():
    """`openflow dashboard --help` should be discoverable via the
    top-level CLI."""
    from openflow.migrate.cli import main as openflow_main
    # We can't actually run `serve` here (would block on uvicorn) — but
    # we can pass --help and verify it doesn't crash.
    with pytest.raises(SystemExit) as exc:
        openflow_main(["dashboard", "--help"])
    assert exc.value.code == 0
