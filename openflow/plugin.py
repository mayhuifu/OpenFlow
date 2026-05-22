"""Pytest plugin entry point. Registered via [project.entry-points.pytest11] in pyproject.toml."""
from __future__ import annotations

from typing import TYPE_CHECKING

from openflow.fixtures import (  # noqa: F401  (re-export for pytest)
    cmw100,
    config,
    dmm_c,
    dmm_v,
    dut,
    results,
    wfg,
)
from openflow.results import ResultsPublisher, write_session_report

if TYPE_CHECKING:
    import pytest

    from openflow.config import OpenFlowConfig


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("openflow", "OpenFlow RF test framework")
    group.addoption("--openflow-config", action="store", default=None,
                    help="Path to OpenFlow YAML configuration file.")
    group.addoption("--openflow-report", action="store", default=None,
                    help="Path to write the JSON session report.")
    group.addoption("--openflow-html-report", action="store", default=None,
                    help="Path to write the HTML session report (V2). "
                         "Requires --openflow-report (the HTML is rendered "
                         "from the JSON output).")


def pytest_configure(config: pytest.Config) -> None:  # noqa: F811
    # Param name MUST be 'config' — pytest hookspec inspects argument names.
    # F811 is suppressed because the shadowing of the re-exported `config`
    # fixture name in this module's namespace is intentional and harmless.
    config.addinivalue_line(
        "markers",
        "testcase(id): mark a test with its testcase ID (e.g. U300B0-RFE-EVT-005)",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    # Initialize the per-session publisher list.
    session._openflow_publishers = []  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    report_path = session.config.getoption("--openflow-report")
    html_path = session.config.getoption("--openflow-html-report")

    # V4: persistence is engaged when the loaded OpenFlowConfig has
    # storage.persist=True. Look it up best-effort — if config wasn't
    # loaded (e.g. the test didn't request the config fixture) we just
    # skip persistence silently.
    persist_to_db = _should_persist_to_db(session)

    if not report_path and not html_path and not persist_to_db:
        return

    # If only HTML or only DB-persist is requested, write JSON to a temp
    # path so the downstream consumers have something to read.
    import tempfile
    json_was_temporary = False
    if not report_path:
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        report_path = tmp.name
        json_was_temporary = True

    publishers: list[ResultsPublisher] = getattr(session, "_openflow_publishers", [])
    write_session_report(
        path=report_path,
        publishers=publishers,
        session_summary={
            "exit_status": int(exitstatus),
            "passed": session.testscollected - session.testsfailed,
            "failed": session.testsfailed,
        },
    )

    if html_path:
        from openflow.report.html import HTMLReportRenderer
        HTMLReportRenderer(report_path).render(html_path)

    if persist_to_db:
        _persist_to_db(session, report_path)

    if json_was_temporary:
        from pathlib import Path
        Path(report_path).unlink(missing_ok=True)


def _should_persist_to_db(session: pytest.Session) -> bool:
    """True iff the loaded OpenFlowConfig has storage.persist=True."""
    cfg = _try_load_config(session)
    if cfg is None:
        return False
    return bool(cfg.storage.persist)


def _try_load_config(session: pytest.Session) -> OpenFlowConfig | None:
    """Best-effort: load the OpenFlow config without requiring the
    fixture to have been requested by any test."""
    from pathlib import Path

    from openflow.config import load_config

    path = session.config.getoption("--openflow-config")
    if not path:
        return None
    try:
        return load_config(Path(path))
    except Exception:
        return None


def _persist_to_db(session: pytest.Session, json_report_path: str) -> None:
    """Ingest the just-written JSON report into SQLite (and optionally
    PostgreSQL if storage.postgres_dsn is set)."""
    import logging
    from pathlib import Path

    from openflow.report.db.sqlite_backend import SQLiteBackend

    log = logging.getLogger(__name__)
    cfg = _try_load_config(session)
    if cfg is None:
        return

    # Default sqlite path is `report.db` next to the JSON report.
    json_path = Path(json_report_path)
    sqlite_path = (Path(cfg.storage.sqlite_path)
                   if cfg.storage.sqlite_path is not None
                   else json_path.parent / "report.db")
    try:
        backend = SQLiteBackend(sqlite_path)
        backend.ensure_schema()
        backend.ingest_json(json_path)
        log.info("V4 persistence: wrote session to %s", sqlite_path)
    except Exception as exc:
        log.warning("V4 persistence: SQLite write failed: %s", exc)

    # Optional best-effort PostgreSQL mirror.
    if cfg.storage.postgres_dsn:
        try:
            from openflow.report.db.postgres_backend import PostgreSQLBackend
            pg = PostgreSQLBackend(cfg.storage.postgres_dsn)
            pg.ensure_schema()
            pg.ingest_json(json_path)
            log.info("V4 persistence: wrote session to PostgreSQL")
        except Exception as exc:
            log.warning("V4 persistence: PostgreSQL write failed (local "
                        "SQLite remains source of truth): %s", exc)
