"""Pydantic models for OpenFlow YAML configuration."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class InstrumentConfig(BaseModel):
    """VISA connection info + optional driver-model selector for an instrument.

    V3 generalization of the V1a ``CMW100Config``. The ``model`` field is
    optional — fixtures fall back to their default driver class when it's
    absent. Example YAML:

        instruments:
          cmw100:
            resource: "TCPIP0::192.168.1.10::INSTR"
            # CMW100 has only one driver, so model is unused
          sa:
            resource: "TCPIP0::192.168.1.20::INSTR"
            model: "keysight_n9020b"   # selects KeysightN9020B over RsFsw
          dmm_c:
            resource: "TCPIP0::192.168.1.30::INSTR"
            # model: defaults to "keysight_34461a"
    """
    model_config = ConfigDict(extra="forbid")

    resource: str = Field(min_length=1,
                          description="PyVISA resource string, e.g. 'TCPIP::192.168.1.100::INSTR'")
    model: str | None = Field(default=None,
                              description="Optional driver-model selector for "
                                          "multi-vendor instruments (e.g. 'keysight_n9020b').")


# V1a backward-compat alias. New code should use InstrumentConfig directly.
CMW100Config = InstrumentConfig


class DutConfig(BaseModel):
    """DUT configuration. type='stub' means the generic Dut base; concrete subclasses
    in V1b are 'u300' (DUT_U300) and 'ft2232h' (DUT_FT2232h_V03)."""
    model_config = ConfigDict(extra="forbid")

    type: Literal["stub", "u300", "ft2232h"] = "stub"
    # FTDI bridge fields (optional — only used when the DUT type involves FT2232H).
    ftdi_address: str = ""
    reg_map_file: str = ""
    emulation: bool = True  # V1a-compatible default


class OpenFlowConfig(BaseModel):
    """Top-level OpenFlow YAML config consumed by the `config` fixture."""
    model_config = ConfigDict(extra="forbid")

    # Instruments — V1a was CMW100 only, V3 generalizes to any SCPI instrument.
    instruments: dict[str, InstrumentConfig]

    # Band + waveform configuration
    band: str
    modulation: str
    rfbw_Hz: int
    dl_freq_pll_Hz: int
    ul_freq_pll_Hz: int
    dl_config: str
    dl_config_active: str
    ul_config: str
    scs_Hz: int
    rb_centre_freq_Hz: int
    freq_offset_dl_Hz: int
    rx_gain_dB: int
    tx_power_dBm: float
    tx_power_backoff_dB: float
    rx_power_backoff_dB: float
    tx_dac_backoff_dBFS: float
    board_config: str

    # Board serials — added in V1c. Optional with safe defaults so existing YAML
    # without these fields continues to load. Used by Calibration_File lookups
    # in the migrated tests (engineer fills these in for real bench runs).
    rfeb_sn: str = ""
    rfhb_sn: str = ""

    # External lookup tables (paths resolved relative to the config file)
    limits_path: Path
    deembedding_path: Path
    calibration_path: Path

    # DUT selection (V1a default: stub returns base Dut; V1b: u300, ft2232h)
    dut: DutConfig = Field(default_factory=DutConfig)


# --- YAML loader ---------------------------------------------------------------


def load_config(path: Path) -> OpenFlowConfig:
    """Load a YAML config file and resolve relative *_path fields against its directory."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"OpenFlow config not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    try:
        cfg = OpenFlowConfig.model_validate(raw)
    except ValidationError as e:
        raise ValueError(f"Invalid config file {path}:\n{e}") from e

    base = path.parent.resolve()
    cfg = cfg.model_copy(update={
        "limits_path": _resolve(base, cfg.limits_path),
        "deembedding_path": _resolve(base, cfg.deembedding_path),
        "calibration_path": _resolve(base, cfg.calibration_path),
    })
    return cfg


def _resolve(base: Path, relative_or_abs: Path) -> Path:
    p = Path(relative_or_abs)
    return p.resolve() if p.is_absolute() else (base / p).resolve()
