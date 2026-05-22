"""V1a placeholder classes for instruments the migrated tests import but do not exercise.

Each class derives from `Instrument` so the migrated test's imports resolve at
collection time. The real driver port for each lands in V2+ when the
corresponding test migrates over. Calling any I/O method raises
`NotImplementedError` with the class name and a pointer to V2.

V1f exception: ``DMM`` is now a re-export alias of the real
``DMMKeysight34461A`` driver. The migrator emits
``from openflow.instruments.stubs import DMM`` for every test that referenced
``UMT_Instruments.DMM`` in OpenTAP, and we keep the symbol available so those
imports keep working — the underlying class is the real driver, not a stub.
Engineers writing new tests should import ``DMMKeysight34461A`` directly.
"""
from __future__ import annotations

from openflow.instruments.base import Instrument
from openflow.instruments.dmm_keysight import DMMKeysight34461A


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


# V1f: DMM is the real Keysight 34461A driver, not a stub. The name is kept here
# for backward compatibility with migrated tests that import `DMM` from this
# module (the migrator emits that import line from UMT_Instruments.DMM rewrites).
DMM = DMMKeysight34461A


class PSU(_UnimplementedInstrument):
    """Power supply unit stub."""


class OSC(_UnimplementedInstrument):
    """Oscilloscope stub."""


class SG(_UnimplementedInstrument):
    """Signal generator stub."""


class SA(_UnimplementedInstrument):
    """Spectrum analyzer stub."""
