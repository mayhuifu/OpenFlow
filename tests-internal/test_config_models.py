import pytest
from pydantic import ValidationError

from openflow.config import CMW100Config, InstrumentConfig, OpenFlowConfig


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


def test_instrument_config_model_field_is_optional():
    """V3: InstrumentConfig.model is optional — absent means use the
    fixture's default driver class."""
    cfg = InstrumentConfig(resource="TCPIP::1::INSTR")
    assert cfg.model is None


def test_instrument_config_accepts_model_field():
    """V3: model field carries the driver-class selector for
    multi-vendor instruments."""
    cfg = InstrumentConfig(resource="TCPIP::1::INSTR", model="keysight_n9020b")
    assert cfg.model == "keysight_n9020b"


def test_cmw100_config_alias_is_instrument_config():
    """V3: CMW100Config is now an alias for InstrumentConfig for backward
    compat. New code should use InstrumentConfig directly."""
    assert CMW100Config is InstrumentConfig


def test_openflow_config_with_model_field_in_yaml():
    """V3 YAML usage — instruments dict can specify model per instrument."""
    cfg = OpenFlowConfig.model_validate({
        "instruments": {
            "cmw100": {"resource": "TCPIP::10.0.0.1::INSTR"},
            "sa": {"resource": "TCPIP::10.0.0.2::INSTR", "model": "rs_fsw"},
        },
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
    assert cfg.instruments["sa"].model == "rs_fsw"
    assert cfg.instruments["cmw100"].model is None


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
