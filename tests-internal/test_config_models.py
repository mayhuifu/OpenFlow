import pytest
from pydantic import ValidationError

from openflow.config import CMW100Config, OpenFlowConfig


def test_cmw100_config_requires_resource():
    cfg = CMW100Config(resource="TCPIP::192.168.1.100::INSTR")
    assert cfg.resource == "TCPIP::192.168.1.100::INSTR"


def test_cmw100_config_rejects_empty_resource():
    with pytest.raises(ValidationError):
        CMW100Config(resource="")


def test_openflow_config_minimal_construction():
    cfg = OpenFlowConfig(
        instruments={"cmw100": CMW100Config(resource="TCPIP::10.0.0.1::INSTR")},
        band="n78",
        modulation="16QAM",
        rfbw_Hz=100_000_000,
        dl_freq_pll_Hz=3_600_000_000,
        ul_freq_pll_Hz=3_500_000_000,
        dl_config="RX0_ANT0",
        dl_config_active="RX0_ANT0",
        ul_config="TX0_ANT0",
        scs_Hz=30_000,
        rb_centre_freq_Hz=3_600_000_000,
        freq_offset_dl_Hz=0,
        rx_gain_dB=30,
        tx_power_dBm=0.0,
        tx_power_backoff_dB=5.0,
        rx_power_backoff_dB=10.0,
        tx_dac_backoff_dBFS=6.0,
        board_config="RFEB1",
        limits_path="configs/limits/U300B0.yaml",
        deembedding_path="configs/deembedding/U300B0.yaml",
        calibration_path="configs/calibration/U300B0.yaml",
    )
    assert cfg.band == "n78"
    assert cfg.rfbw_Hz == 100_000_000
    assert cfg.instruments["cmw100"].resource.startswith("TCPIP")


def test_openflow_config_rejects_extra_fields():
    with pytest.raises(ValidationError):
        OpenFlowConfig.model_validate({
            "instruments": {"cmw100": {"resource": "TCPIP::1::INSTR"}},
            "band": "n78",
            "modulation": "16QAM",
            "rfbw_Hz": 100_000_000,
            "dl_freq_pll_Hz": 3_600_000_000,
            "ul_freq_pll_Hz": 3_500_000_000,
            "dl_config": "RX0_ANT0",
            "dl_config_active": "RX0_ANT0",
            "ul_config": "TX0_ANT0",
            "scs_Hz": 30_000,
            "rb_centre_freq_Hz": 3_600_000_000,
            "freq_offset_dl_Hz": 0,
            "rx_gain_dB": 30,
            "tx_power_dBm": 0.0,
            "tx_power_backoff_dB": 5.0,
            "rx_power_backoff_dB": 10.0,
            "tx_dac_backoff_dBFS": 6.0,
            "board_config": "RFEB1",
            "limits_path": "x",
            "deembedding_path": "y",
            "calibration_path": "z",
            "secret_extra_field": "should reject",
        })
