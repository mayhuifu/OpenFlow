"""Verify the user-facing fixtures resolve and behave correctly."""
import json
from pathlib import Path

import pytest

VALID_CONFIG = """
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
rb_centre_freq_Hz: 3600000000
freq_offset_dl_Hz: 0
rx_gain_dB: 30
tx_power_dBm: 0.0
tx_power_backoff_dB: 5.0
rx_power_backoff_dB: 10.0
tx_dac_backoff_dBFS: 6.0
board_config: RFEB1
limits_path: limits.yaml
deembedding_path: deembedding.yaml
calibration_path: calibration.yaml
"""


def test_config_fixture_loads_yaml(pytester: pytest.Pytester, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(VALID_CONFIG)
    pytester.makepyfile("""
        def test_config_resolves(config):
            assert config.band == "n78"
            assert config.rfbw_Hz == 100_000_000
            assert config.instruments["cmw100"].resource.startswith("MOCK")
    """)
    result = pytester.runpytest(f"--openflow-config={cfg}")
    assert result.ret == 0


def test_cmw100_fixture_uses_emulation_for_MOCK_resource(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(VALID_CONFIG)
    pytester.makepyfile("""
        def test_cmw100_emulation(cmw100):
            assert cmw100.is_emulation is True
            # Real method call works in emulation:
            cmw100.setup_NrTx(
                in_band="n78", in_freq_pll_Hz=3_600_000_000, in_rfbw_Hz=100_000_000,
                in_rb_centre_freq_Hz=3_600_000_000, in_tx_power_dBm=0.0,
                in_tx_power_backoff_dB=5.0, in_modulation="16QAM",
                in_rf_connector=1, in_scs_Hz=30_000)
    """)
    result = pytester.runpytest(f"--openflow-config={cfg}")
    assert result.ret == 0


def test_dut_fixture_is_Dut_instance(pytester: pytest.Pytester, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(VALID_CONFIG)
    pytester.makepyfile("""
        from openflow.dut.base import Dut

        def test_dut_type(dut):
            assert isinstance(dut, Dut)
    """)
    result = pytester.runpytest(f"--openflow-config={cfg}")
    assert result.ret == 0


def test_wfg_dmm_c_dmm_v_fixtures_resolve(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(VALID_CONFIG)
    pytester.makepyfile("""
        from openflow.instruments.stubs import WFG, DMM

        def test_stub_fixtures(wfg, dmm_c, dmm_v):
            assert isinstance(wfg, WFG)
            assert isinstance(dmm_c, DMM)
            assert isinstance(dmm_v, DMM)
    """)
    result = pytester.runpytest(f"--openflow-config={cfg}")
    assert result.ret == 0


def test_results_fixture_publishes_to_session_report(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(VALID_CONFIG)
    report = tmp_path / "report.json"
    pytester.makepyfile("""
        import pytest

        @pytest.mark.testcase("X-001")
        def test_publishes(results):
            results.publish(gain=10, delta=0.1)
            results.publish(gain=20, delta=0.05)
    """)
    result = pytester.runpytest(f"--openflow-config={cfg}",
                                f"--openflow-report={report}")
    assert result.ret == 0
    payload = json.loads(report.read_text())
    assert len(payload["tests"]) == 1
    assert payload["tests"][0]["testcase_id"] == "X-001"
    assert len(payload["tests"][0]["records"]) == 2
    assert payload["tests"][0]["records"][0]["gain"] == 10
