from pathlib import Path

import pytest


def test_openflow_config_option_is_registered(pytester: pytest.Pytester) -> None:
    pytester.makeini("""
        [pytest]
    """)
    result = pytester.runpytest("--help")
    assert "--openflow-config" in result.stdout.str()
    assert "--openflow-report" in result.stdout.str()
    assert "--openflow-html-report" in result.stdout.str()


def test_testcase_marker_is_registered(pytester: pytest.Pytester) -> None:
    pytester.makepyfile("""
        import pytest

        @pytest.mark.testcase("X-Y-001")
        def test_marked():
            pass
    """)
    result = pytester.runpytest("--strict-markers")
    assert result.ret == 0


def test_session_finish_writes_empty_report_when_option_given(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    pytester.makepyfile("""
        def test_trivial():
            assert 1 == 1
    """)
    report = tmp_path / "report.json"
    result = pytester.runpytest(f"--openflow-report={report}")
    assert result.ret == 0
    assert report.exists()


def test_html_report_option_writes_html(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    """V2: --openflow-html-report writes an HTML file alongside the JSON."""
    pytester.makepyfile("""
        def test_trivial():
            assert 1 == 1
    """)
    report = tmp_path / "report.json"
    html = tmp_path / "report.html"
    result = pytester.runpytest(
        f"--openflow-report={report}",
        f"--openflow-html-report={html}",
    )
    assert result.ret == 0
    assert report.exists()
    assert html.exists()
    content = html.read_text()
    assert "<!DOCTYPE html>" in content
    assert "OpenFlow report" in content


def test_html_report_option_works_without_explicit_json(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    """V2: --openflow-html-report alone (no --openflow-report) still works
    by writing the JSON to a temp file and cleaning it up after."""
    pytester.makepyfile("""
        def test_trivial():
            assert 1 == 1
    """)
    html = tmp_path / "report.html"
    result = pytester.runpytest(f"--openflow-html-report={html}")
    assert result.ret == 0
    assert html.exists()
