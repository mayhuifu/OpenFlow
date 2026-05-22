"""Keysight 33500B waveform generator SCPI driver.

The 33500B series (33509B/33511B/33512B/33519B/33521B/33522B) is the
go-to arbitrary waveform generator on RF benches. This driver targets
the 33500B; same SCPI surface applies to the 33600A series with minor
differences.

API surface (consumed by migrated EVT tests):

    load_arb_file(filepath, sample_rate, name)
    set_arb_sample_rate(rate_Hz, channel)
    set_arb_output_amplitude_Vpp(amp, channel)
    output_on(channel)
    output_off(channel)
    set_sync_mode(ext)               -- TRIGger:SOURce EXT|IMM
"""
from __future__ import annotations

from pathlib import Path

from openflow.instruments.scpi import SCPIInstrument


class Keysight33500B(SCPIInstrument):
    """Keysight 33500B 2-channel arbitrary waveform generator."""

    _IDN_HINT = "Keysight Technologies,33522B,EMU0,A.00.00-EMU"

    def load_arb_file(self, filepath: Path | str, *,
                      sample_rate_Hz: float = 1e6,
                      name: str = "ARB1",
                      channel: int = 1) -> None:
        """Upload an arbitrary waveform file to the WFG's memory.

        ``filepath`` is the path on the instrument (or USB) — the WFG
        reads the file directly. For network uploads use
        ``MMEMory:LOAD:DATA`` (not implemented yet — pure file-based
        loading is the common bench path).
        """
        ch = self._channel_prefix(channel)
        self.write(f'{ch}DATA:ARBitrary:LOAD "{filepath}"')
        self.write(f"{ch}FUNCtion:ARBitrary:SRATe {sample_rate_Hz:g}")
        self.write(f'{ch}FUNCtion:ARBitrary "{name}"')
        self.write(f"{ch}FUNCtion ARB")

    def set_arb_sample_rate(self, rate_Hz: float, *, channel: int = 1) -> None:
        """Set the ARB playback sample rate."""
        ch = self._channel_prefix(channel)
        self.write(f"{ch}FUNCtion:ARBitrary:SRATe {rate_Hz:g}")

    def set_arb_output_amplitude_Vpp(self, amp_Vpp: float, *,
                                     channel: int = 1) -> None:
        """Set the output amplitude in peak-to-peak volts."""
        ch = self._channel_prefix(channel)
        self.write(f"{ch}VOLTage {amp_Vpp:g}")

    def output_on(self, channel: int = 1) -> None:
        """Enable the named channel's output."""
        ch = self._channel_prefix(channel)
        self.write(f"{ch}OUTPut ON")

    def output_off(self, channel: int = 1) -> None:
        """Disable the named channel's output."""
        ch = self._channel_prefix(channel)
        self.write(f"{ch}OUTPut OFF")

    def set_sync_mode(self, *, ext: bool, channel: int = 1) -> None:
        """Configure trigger source: external trigger vs. immediate."""
        ch = self._channel_prefix(channel)
        source = "EXT" if ext else "IMM"
        self.write(f"{ch}TRIGger:SOURce {source}")

    # --- internals --------------------------------------------------------
    @staticmethod
    def _channel_prefix(channel: int) -> str:
        """SCPI channel selector — 'SOURce1:' or 'SOURce2:' for the
        33500B's 2-channel models, '' for single-channel models."""
        if channel not in (1, 2):
            raise ValueError(f"Keysight33500B: channel must be 1 or 2 "
                             f"(got {channel!r})")
        return f"SOURce{channel}:"
