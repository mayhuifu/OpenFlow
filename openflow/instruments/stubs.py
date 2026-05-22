"""V1a placeholder classes for instruments the migrated tests import.

Each name here is either a placeholder ``_UnimplementedInstrument`` subclass
(for instruments no migrated test currently exercises) or an alias to a real
driver class (for instruments that V1f/V3 ported). The migrator emits
``from openflow.instruments.stubs import <NAME>`` for every test that referenced
``UMT_Instruments.<NAME>`` in OpenTAP, so we keep all the symbols available
here.

V1f / V3 alias targets:

  DMM  -> DMMKeysight34461A     (V1f)
  SG   -> RsSmw200a             (V3)
  SA   -> KeysightN9020B        (V3 default; rs_fsw is the alternative)
  WFG  -> Keysight33500B        (V3)

Remaining stubs (no migrated test uses them yet — will be aliased when needed):

  PSU  -> _UnimplementedInstrument
  OSC  -> _UnimplementedInstrument

Engineers writing new tests should import the concrete driver classes
directly rather than going through these aliases.
"""
from __future__ import annotations

from openflow.instruments.base import Instrument
from openflow.instruments.dmm_keysight import DMMKeysight34461A
from openflow.instruments.sa_keysight_n9020b import KeysightN9020B
from openflow.instruments.sg_rs_smw200a import RsSmw200a
from openflow.instruments.wfg_keysight_33500b import Keysight33500B


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


# V1f: DMM is the real Keysight 34461A driver, not a stub.
DMM = DMMKeysight34461A

# V3: SG/SA/WFG are now real drivers. The default SA model is Keysight N9020B;
# engineers running an R&S FSW select it via instruments.sa.model: rs_fsw.
SG = RsSmw200a
SA = KeysightN9020B
WFG = Keysight33500B


class PSU(_UnimplementedInstrument):
    """Power supply unit stub."""


class OSC(_UnimplementedInstrument):
    """Oscilloscope stub."""
