"""Tests for openflow.rfengine.calibration_file.

Ported from U300_RFEngine/Calibration_File.py. The class is essentially a
YAML-backed nested dict with helpers for inserting and reading TX/RX
calibration data per band/bandwidth/antenna.

The TX EVM test in V1b calls:
    cal_file.get_iq_dc_offset(in_band_num, in_rfbw_Hz)
    cal_file.get_iq_gain_phase_imbalance(in_band_num, in_rfbw_Hz)
so we smoke-test those two specifically.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from openflow.rfengine.calibration_file import Calibration_File


SAMPLE_YAML = """
general:
  calibration_file_version: "v0.2.0"
  calibration_date: "2026-01-01"

tx_carriers:
  - band: 41
    tx_cal_data:
      i_q_dc_imbalance:
        per_bw:
          - bw_mhz: 10
            per_freq:
              - freq_khz: 0
                i_dc_uA: 500
                q_dc_uA: -300
      iqmm_gain_phase:
        per_bw:
          - bw_mhz: 10
            per_freq:
              - freq_khz: 0
                gain_db: 50
                phase_degree: 25
"""


@pytest.fixture()
def yaml_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "cal.yaml"
    cfg.write_text(SAMPLE_YAML)
    return cfg


def test_can_be_instantiated(yaml_config: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    assert cal.filename == str(yaml_config)
    assert isinstance(cal.config, dict)
    assert cal.err == ""


def test_constructor_substitutes_rf_and_bb_id_placeholders(tmp_path: Path) -> None:
    target = tmp_path / "cal__RF123__BB456.yaml"
    target.write_text("general: {}\n")
    cal = Calibration_File(
        filename=str(tmp_path / "cal_<RF_ID>_<BB_ID>.yaml"),
        rf_sn="RF123",
        bb_sn="BB456",
    )
    assert cal.filename == str(target)


def test_missing_file_yields_empty_config(tmp_path: Path) -> None:
    cal = Calibration_File(str(tmp_path / "does_not_exist.yaml"))
    assert cal.config == {}
    assert "Could not load File" in cal.err


def test_get_and_set_round_trip(yaml_config: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    cal.set("custom", "param", 42)
    assert cal.get("custom", "param") == 42


def test_get_returns_zero_for_unknown_keys(yaml_config: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    assert cal.get("nonexistent_group", "anything") == 0


def test_get_band_bandwidth_round_trip(yaml_config: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    cal.set_band_bandwidth("TX", "n1", 10e6, "tx_iq_gain_imbalance_dB", 0.02)
    assert cal.get_band_bandwidth("TX", "n1", 10e6, "tx_iq_gain_imbalance_dB") == 0.02


def test_get_iq_dc_offset_known_band(yaml_config: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    i_offset_A, q_offset_A = cal.get_iq_dc_offset(in_band_num=41, in_rfbw_Hz=10e6)
    # 500 uA * 1e-7 == 5e-5 A; -300 uA * 1e-7 == -3e-5 A.
    assert i_offset_A == pytest.approx(500 * 1e-7)
    assert q_offset_A == pytest.approx(-300 * 1e-7)


def test_get_iq_gain_phase_imbalance_known_band(yaml_config: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    gain_dB, phase_deg = cal.get_iq_gain_phase_imbalance(
        in_band_num=41, in_rfbw_Hz=10e6
    )
    # gain_db stored as gain*100; phase_degree stored as deg*10.
    assert gain_dB == pytest.approx(50 / 100)
    assert phase_deg == pytest.approx(25 / 10)


def test_get_iq_dc_offset_unknown_band_returns_zero(yaml_config: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    i_offset_A, q_offset_A = cal.get_iq_dc_offset(in_band_num=999, in_rfbw_Hz=10e6)
    assert i_offset_A == 0
    assert q_offset_A == 0


def test_save_writes_yaml(yaml_config: Path, tmp_path: Path) -> None:
    cal = Calibration_File(str(yaml_config))
    cal.save(room_temp_C10=250)
    assert yaml_config.exists()
    reloaded = yaml.safe_load(yaml_config.read_text())
    assert reloaded["general"]["calibration_temperature_room"] == 2500
    assert reloaded["general"]["calibration_file_version"] == "v0.2.0"
