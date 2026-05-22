"""V1a placeholder classes for instruments the migrated tests import but do not exercise.

Each class derives from `Instrument` so the migrated test's imports resolve at
collection time. The real driver port for each lands in V2 when the corresponding
test migrates over. Calling any I/O method raises `NotImplementedError` with the
class name and a pointer to V2.
"""
from __future__ import annotations

from openflow.instruments.base import Instrument


class _UnimplementedInstrument(Instrument):
    """Common parent — V1a placeholder behavior shared by all stubs."""

    def open(self) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}: V1a placeholder. Real port lands in V2.")

    def close(self) -> None:
        # No-op so context-manager teardown succeeds even if open() was never called.
        return None

    def write(self, scpi: str) -> None:
        raise NotImplementedError(
            f"{type(self).__name__}.write: V1a placeholder. Real port lands in V2.")

    def query(self, scpi: str) -> str:
        raise NotImplementedError(
            f"{type(self).__name__}.query: V1a placeholder. Real port lands in V2.")


class WFG(_UnimplementedInstrument):
    """Waveform generator stub."""


class DMM(_UnimplementedInstrument):
    """Digital multimeter stub."""


class PSU(_UnimplementedInstrument):
    """Power supply unit stub."""


class OSC(_UnimplementedInstrument):
    """Oscilloscope stub."""


class SG(_UnimplementedInstrument):
    """Signal generator stub."""


class SA(_UnimplementedInstrument):
    """Spectrum analyzer stub."""
