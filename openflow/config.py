"""Pydantic models for OpenFlow YAML configuration."""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CMW100Config(BaseModel):
    """VISA connection info for a CMW100 instrument."""
    model_config = ConfigDict(extra="forbid")

    resource: str = Field(min_length=1,
                          description="PyVISA resource string, e.g. 'TCPIP::192.168.1.100::INSTR'")


class OpenFlowConfig(BaseModel):
    """Top-level OpenFlow YAML config consumed by the `config` fixture."""
    model_config = ConfigDict(extra="forbid")

    # Instruments (V1a: CMW100 only)
    instruments: dict[str, CMW100Config]

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

    # External lookup tables (paths resolved relative to the config file)
    limits_path: Path
    deembedding_path: Path
    calibration_path: Path


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
