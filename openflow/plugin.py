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
    if not report_path and not html_path:
        return

    # If only HTML is requested, write JSON to a sibling temp path so the
    # HTML renderer has something to consume — and clean it up after.
    import tempfile
    json_was_temporary = False
    if not report_path and html_path:
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

    if json_was_temporary:
        from pathlib import Path
        Path(report_path).unlink(missing_ok=True)
