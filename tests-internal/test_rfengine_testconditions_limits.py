"""Tests for openflow.rfengine.testconditions_limits.

Ported from U300_RFEngine/Testconditions_Limits.py. The class loads a YAML
of testcase -> band -> bandwidth -> param mappings and exposes ``get(tc,
band, bandwidth_Hz, param)`` plus ``get_band_modulation(tc, band,
modulation, param)``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from openflow.rfengine.testconditions_limits import Testconditions_Limits


SAMPLE_YAML = """
DVT_5G_NR_Tx_Maximum_Output_Power:
  default:
    default:
      POUT_MAX: 23.0
    "5":
      POUT_MAX: 22.0
  n41:
    default:
      POUT_MAX: 25.0
    "10":
      POUT_MAX: 26.0

DVT_5G_NR_Tx_EVM:
  default:
    QPSK:
      EVM_MAX: 17.5
      default:
        EVM_MAX: 17.5
    default:
      QPSK:
        EVM_MAX: 17.5
      default:
        EVM_MAX: 8.0
  n78:
    "256QAM":
      EVM_MAX: 3.5
    default:
      EVM_MAX: 8.0
"""


@pytest.fixture()
def yaml_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "limits.yaml"
    cfg.write_text(SAMPLE_YAML)
    return cfg


def test_can_be_instantiated(yaml_config: Path) -> None:
    tcl = Testconditions_Limits(str(yaml_config))
    assert tcl.filename == str(yaml_config)
    assert isinstance(tcl.config, dict)
    assert tcl.err == ""


def test_get_exact_band_and_bandwidth(yaml_config: Path) -> None:
    tcl = Testconditions_Limits(str(yaml_config))
    val = tcl.get(
        tc="DVT_5G_NR_Tx_Maximum_Output_Power",
        band="n41",
        bandwidth_Hz=10e6,
        param="POUT_MAX",
    )
    assert val == pytest.approx(26.0)


def test_get_falls_back_to_band_default_bw(yaml_config: Path) -> None:
    tcl = Testconditions_Limits(str(yaml_config))
    val = tcl.get(
        tc="DVT_5G_NR_Tx_Maximum_Output_Power",
        band="n41",
        bandwidth_Hz=20e6,  # not in YAML -> default
        param="POUT_MAX",
    )
    assert val == pytest.approx(25.0)


def test_get_falls_back_to_overall_default_band(yaml_config: Path) -> None:
    tcl = Testconditions_Limits(str(yaml_config))
    val = tcl.get(
        tc="DVT_5G_NR_Tx_Maximum_Output_Power",
        band="nUNKNOWN",
        bandwidth_Hz=5e6,
        param="POUT_MAX",
    )
    assert val == pytest.approx(22.0)


def test_get_returns_none_for_missing_param(yaml_config: Path) -> None:
    tcl = Testconditions_Limits(str(yaml_config))
    val = tcl.get(
        tc="DVT_5G_NR_Tx_Maximum_Output_Power",
        band="n41",
        bandwidth_Hz=10e6,
        param="MISSING_PARAM",
    )
    assert val is None
    assert "MISSING_PARAM" in tcl.err


def test_get_band_modulation_exact_match(yaml_config: Path) -> None:
    tcl = Testconditions_Limits(str(yaml_config))
    val = tcl.get_band_modulation(
        tc="DVT_5G_NR_Tx_EVM",
        band="n78",
        modulation="256QAM",
        param="EVM_MAX",
    )
    assert val == pytest.approx(3.5)
