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


def test_report_options_auto_create_parent_dir(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    """v1.0.0-rc3 bench-feedback fix: ``--openflow-report=reports/X.json``
    and ``--openflow-html-report=reports/X.html`` must auto-create
    the ``reports/`` directory if it doesn't exist. Previously crashed
    pytest_sessionfinish with FileNotFoundError on bench machines that
    didn't pre-mkdir."""
    pytester.makepyfile("""
        def test_trivial():
            assert 1 == 1
    """)
    json_report = tmp_path / "missing-dir" / "subdir" / "report.json"
    html_report = tmp_path / "missing-dir" / "subdir" / "report.html"
    assert not json_report.parent.exists()  # pre-condition

    result = pytester.runpytest(
        f"--openflow-report={json_report}",
        f"--openflow-html-report={html_report}",
    )
    assert result.ret == 0
    assert json_report.exists()
    assert html_report.exists()


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


# --- V4: storage.persist plugin integration -----------------------------

_VALID_CONFIG_NO_STORAGE = """\
instruments:
  cmw100:
    resource: "MOCK::CMW100::INSTR"
band: n78
modulation: "16QAM"
rfbw_Hz: 100000000
dl_freq_pll_Hz: 3600000000
ul_freq_pll_Hz: 3500000000
dl_config: RX0_ANT0
dl_config_active: RX0_ANT0
ul_config: TX0_ANT0
scs_Hz: 30000
rb_centre_freq_Hz: 3500000000
freq_offset_dl_Hz: 0
rx_gain_dB: 30
tx_power_dBm: 0.0
tx_power_backoff_dB: 5.0
rx_power_backoff_dB: 10.0
tx_dac_backoff_dBFS: 6.0
board_config: RFEB1
limits_path: ./limits.yaml
deembedding_path: ./deembedding.yaml
calibration_path: ./calibration.yaml
"""


def test_storage_persist_off_by_default_no_db_written(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    """V4: storage.persist defaults to False — no report.db created."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(_VALID_CONFIG_NO_STORAGE)
    pytester.makepyfile("""
        def test_trivial():
            assert 1 == 1
    """)
    report = tmp_path / "report.json"
    result = pytester.runpytest(
        f"--openflow-config={cfg}", f"--openflow-report={report}")
    assert result.ret == 0
    assert report.exists()
    # No sibling report.db.
    assert not (tmp_path / "report.db").exists()


def test_storage_persist_true_writes_sqlite(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    """V4: storage.persist=true writes a sibling report.db alongside JSON."""
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(_VALID_CONFIG_NO_STORAGE + "\nstorage:\n  persist: true\n")
    pytester.makepyfile("""
        def test_trivial():
            assert 1 == 1
    """)
    report = tmp_path / "report.json"
    result = pytester.runpytest(
        f"--openflow-config={cfg}", f"--openflow-report={report}")
    assert result.ret == 0
    db = tmp_path / "report.db"
    assert db.exists()
    # Read back: one session row.
    from openflow.report.db.sqlite_backend import SQLiteBackend
    backend = SQLiteBackend(db)
    assert len(backend.list_sessions()) == 1


def test_storage_persist_writes_db_even_without_json_report(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    """V4: --openflow-report omitted but storage.persist=true still works
    — temp JSON, ingest, cleanup."""
    cfg = tmp_path / "cfg.yaml"
    sqlite_path = tmp_path / "custom-report.db"
    cfg.write_text(
        _VALID_CONFIG_NO_STORAGE
        + f"\nstorage:\n  persist: true\n  sqlite_path: {sqlite_path}\n"
    )
    pytester.makepyfile("""
        def test_trivial():
            assert 1 == 1
    """)
    result = pytester.runpytest(f"--openflow-config={cfg}")
    assert result.ret == 0
    assert sqlite_path.exists()
