"""R&S FSW spectrum analyzer SCPI driver.

Subclass of :class:`SpectrumAnalyzerBase`. Inherits all cross-vendor
methods; overrides only ``_IDN_HINT`` (and any future R&S-specific
behavior — e.g. R&S has a slightly different ACLR measurement command set).

Same driver applies to:
- FSW8 / FSW13 / FSW26 / FSW43 (different frequency ranges, same SCPI)
- FSWP (phase-noise variant — most commands work, additional phase-noise
  commands not yet ported)
"""
from openflow.instruments.sa_base import SpectrumAnalyzerBase


class RsFsw(SpectrumAnalyzerBase):
    """R&S FSW spectrum analyzer."""

    _IDN_HINT = "Rohde&Schwarz,FSW,EMU0,1.00.00-EMU"
