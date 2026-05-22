"""Pytest plugin entry point. Registered via [project.entry-points.pytest11] in pyproject.toml."""
from __future__ import annotations

from typing import TYPE_CHECKING

from openflow.results import ResultsPublisher, write_session_report

if TYPE_CHECKING:
    import pytest


def pytest_addoption(parser: "pytest.Parser") -> None:
    group = parser.getgroup("openflow", "OpenFlow RF test framework")
    group.addoption("--openflow-config", action="store", default=None,
                    help="Path to OpenFlow YAML configuration file.")
    group.addoption("--openflow-report", action="store", default=None,
                    help="Path to write the JSON session report.")


def pytest_configure(config: "pytest.Config") -> None:
    config.addinivalue_line(
        "markers",
        "testcase(id): mark a test with its testcase ID (e.g. U300B0-RFE-EVT-005)",
    )


def pytest_sessionstart(session: "pytest.Session") -> None:
    # Initialize the per-session publisher list.
    session._openflow_publishers = []  # type: ignore[attr-defined]


def pytest_sessionfinish(session: "pytest.Session", exitstatus: int) -> None:
    report_path = session.config.getoption("--openflow-report")
    if not report_path:
        return
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
