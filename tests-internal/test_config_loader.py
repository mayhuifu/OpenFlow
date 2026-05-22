from pathlib import Path

import pytest

from openflow.config import OpenFlowConfig, load_config


VALID_YAML = """
instruments:
  cmw100:
    resource: "TCPIP::192.168.1.100::INSTR"
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


def test_load_config_parses_valid_yaml(tmp_path: Path):
    cfg_file = tmp_path / "cfg.yaml"
    cfg_file.write_text(VALID_YAML)

    cfg = load_config(cfg_file)
    assert isinstance(cfg, OpenFlowConfig)
    assert cfg.band == "n78"
    assert cfg.modulation == "16QAM"
    assert cfg.instruments["cmw100"].resource == "TCPIP::192.168.1.100::INSTR"


def test_load_config_resolves_relative_paths(tmp_path: Path):
    cfg_file = tmp_path / "subdir" / "cfg.yaml"
    cfg_file.parent.mkdir()
    cfg_file.write_text(VALID_YAML)

    cfg = load_config(cfg_file)
    # limits_path is "limits.yaml" in the YAML; should resolve relative to cfg_file's directory.
    assert cfg.limits_path == (tmp_path / "subdir" / "limits.yaml").resolve()


def test_load_config_raises_for_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "does-not-exist.yaml")


def test_load_config_raises_for_invalid_yaml_schema(tmp_path: Path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("instruments: not_a_dict\nband: n78\n")
    with pytest.raises(ValueError) as exc:
        load_config(bad)
    assert "validation" in str(exc.value).lower() or "instruments" in str(exc.value).lower()
