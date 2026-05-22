"""End-to-end integration: plugin + fixtures + real CMW100 (emulation) → report.json."""
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest


INTEGRATION_CONFIG = dedent("""
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
""")


SYNTHETIC_TEST_FILE = dedent('''
    """Synthetic TX EVM round-trip test — exercises the real CMW100 emulation mode."""
    import pytest


    @pytest.mark.testcase("U300B0-MOCK-INT-001")
    @pytest.mark.parametrize("target_power", [-10.0, 0.0, 10.0])
    def test_emulation_tx_evm_round_trip(cmw100, config, results, target_power):
        cmw100.setup_NrTx(
            in_band=config.band,
            in_freq_pll_Hz=config.ul_freq_pll_Hz,
            in_rfbw_Hz=config.rfbw_Hz,
            in_rb_centre_freq_Hz=config.rb_centre_freq_Hz,
            in_tx_power_dBm=target_power,
            in_tx_power_backoff_dB=config.tx_power_backoff_dB,
            in_modulation=config.modulation,
            in_rf_connector=1,
            in_scs_Hz=config.scs_Hz,
        )
        cmw100.meas_NrTxAll()
        reported_power = cmw100.meas_NrTxPower(use_cached=True)
        reported_evm = cmw100.meas_NrTxEVM(use_cached=True)

        results.publish(target_power_dBm=target_power,
                        reported_power_dBm=reported_power,
                        reported_evm_pct=reported_evm)

        # Emulation returns 23+rand for power, 2+rand for EVM (per the original
        # CMW100A.py emulation guards). Bounds are loose to tolerate randomness.
        assert 22.5 < reported_power < 24.5, f"Power {reported_power} out of emulation bounds"
        assert 1.5 < reported_evm < 3.5, f"EVM {reported_evm} out of emulation bounds"
''')


def test_full_session_against_emulation_cmw100(
        pytester: pytest.Pytester, tmp_path: Path) -> None:
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(INTEGRATION_CONFIG)
    pytester.makepyfile(SYNTHETIC_TEST_FILE)
    report = tmp_path / "report.json"

    result = pytester.runpytest(
        f"--openflow-config={cfg}",
        f"--openflow-report={report}",
        "-v",
    )
    result.assert_outcomes(passed=3)
    assert report.exists(), f"Expected {report} to be written"

    payload = json.loads(report.read_text())
    assert payload["session"]["exit_status"] == 0
    assert payload["session"]["passed"] == 3
    assert payload["session"]["failed"] == 0
    assert len(payload["tests"]) == 3, "Expected 3 parametrized test entries"
    assert all(t["testcase_id"] == "U300B0-MOCK-INT-001" for t in payload["tests"])

    # Check that each parametrized iteration recorded the right target power.
    targets = sorted(t["records"][0]["target_power_dBm"] for t in payload["tests"])
    assert targets == [-10.0, 0.0, 10.0]

    # Each record should have a timestamp ending in 'Z'.
    for t in payload["tests"]:
        assert t["records"][0]["timestamp"].endswith("Z")
