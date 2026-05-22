"""Keysight N9020B MXA spectrum analyzer SCPI driver.

Subclass of :class:`SpectrumAnalyzerBase`. Inherits all cross-vendor
methods; overrides only ``_IDN_HINT`` (and any future Keysight-specific
behavior — e.g. screenshot which uses ``:MMEMory:STORe:SCReen`` on
Keysight vs ``:HCOPy:DEVice:LANGuage`` on R&S).

Same driver applies to:
- N9020A (with minor SCPI tweaks for older firmware — subclass further)
- N9030B (PXA) — same SCPI family
- N9040B (UXA) — same SCPI family
"""
from openflow.instruments.sa_base import SpectrumAnalyzerBase


class KeysightN9020B(SpectrumAnalyzerBase):
    """Keysight N9020B MXA spectrum analyzer."""

    _IDN_HINT = "Keysight Technologies,N9020B,EMU0,A.00.00-EMU"
