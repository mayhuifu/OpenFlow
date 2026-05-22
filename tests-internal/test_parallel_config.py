"""Tests for V5b parallel-run config schema."""
from openflow.config import OpenFlowConfig, ParallelConfig, ParallelDutConfig


def test_parallel_config_defaults_to_empty():
    cfg = ParallelConfig()
    assert cfg.duts == []
    assert cfg.shared_instruments == []


def test_parallel_dut_config_requires_tag():
    cfg = ParallelDutConfig(tag="dut_1", type="u300", emulation=True)
    assert cfg.tag == "dut_1"
    assert cfg.type == "u300"


def test_openflow_config_loads_with_parallel_section():
    cfg = OpenFlowConfig.model_validate({
        "instruments": {"cmw100": {"resource": "TCPIP::1::INSTR"}},
        "band": "n78", "modulation": "16QAM", "rfbw_Hz": 100_000_000,
        "dl_freq_pll_Hz": 3_600_000_000, "ul_freq_pll_Hz": 3_500_000_000,
        "dl_config": "RX0_ANT0", "dl_config_active": "RX0_ANT0",
        "ul_config": "TX0_ANT0", "scs_Hz": 30_000,
        "rb_centre_freq_Hz": 3_600_000_000, "freq_offset_dl_Hz": 0,
        "rx_gain_dB": 30, "tx_power_dBm": 0.0, "tx_power_backoff_dB": 5.0,
        "rx_power_backoff_dB": 10.0, "tx_dac_backoff_dBFS": 6.0,
        "board_config": "RFEB1",
        "limits_path": "x", "deembedding_path": "y", "calibration_path": "z",
        "parallel": {
            "duts": [
                {"tag": "dut_1", "type": "u300", "emulation": True},
                {"tag": "dut_2", "type": "u300", "emulation": True},
            ],
            "shared_instruments": ["cmw100"],
        },
    })
    assert len(cfg.parallel.duts) == 2
    assert cfg.parallel.duts[0].tag == "dut_1"
    assert cfg.parallel.shared_instruments == ["cmw100"]


def test_openflow_config_without_parallel_defaults_to_empty():
    cfg = OpenFlowConfig.model_validate({
        "instruments": {"cmw100": {"resource": "TCPIP::1::INSTR"}},
        "band": "n78", "modulation": "16QAM", "rfbw_Hz": 100_000_000,
        "dl_freq_pll_Hz": 3_600_000_000, "ul_freq_pll_Hz": 3_500_000_000,
        "dl_config": "RX0_ANT0", "dl_config_active": "RX0_ANT0",
        "ul_config": "TX0_ANT0", "scs_Hz": 30_000,
        "rb_centre_freq_Hz": 3_600_000_000, "freq_offset_dl_Hz": 0,
        "rx_gain_dB": 30, "tx_power_dBm": 0.0, "tx_power_backoff_dB": 5.0,
        "rx_power_backoff_dB": 10.0, "tx_dac_backoff_dBFS": 6.0,
        "board_config": "RFEB1",
        "limits_path": "x", "deembedding_path": "y", "calibration_path": "z",
    })
    assert cfg.parallel.duts == []
    assert cfg.parallel.shared_instruments == []
