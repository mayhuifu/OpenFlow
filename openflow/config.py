"""Pydantic models for OpenFlow YAML configuration."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


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
