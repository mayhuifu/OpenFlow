"""Keysight 34461A DMM SCPI driver.

The Keysight 34461A is the workhorse 6½-digit benchtop DMM and the most common
DMM in RF benches we encounter. This driver targets that model specifically but
the SCPI command set is largely shared by the 34460A / 34465A / 34470A and most
other Keysight 344xxA series — engineers using a different model can subclass
``DMMKeysight34461A`` and override ``_IDN_HINT`` plus any model-specific
commands without rewriting the EVT-helper-facing API.

API contract (consumed by ``openflow.rfengine.evt_base.setup_dmm`` /
``get_dmm``):

    set_mode(isVoltage: bool, isDc: bool) -> None
    set_range_current(range_A: float) -> None
    set_range_voltage(range_V: float) -> None
    get_measurement() -> float

Plus the standard ``SCPIInstrument`` contract (``open`` / ``close`` /
``write`` / ``query`` / ``identify`` / ``drain_errors``) inherited from
``openflow.instruments.scpi``.

V3 refactor: the pyvisa session lifecycle + ``is_emulation`` SCPI-recording
infrastructure that lived in this module ad-hoc was hoisted into
``openflow.instruments.scpi.SCPIInstrument`` so the new V3 SG / SA / WFG
drivers share it. Behavior unchanged — all 12 V1f DMM tests still pass.
"""
from __future__ import annotations

import math

from openflow.instruments.scpi import SCPIInstrument

# Canned emulation reading. Deterministic so test assertions are stable;
# plausible enough that downstream consumers don't mistake it for an error
# sentinel.
_EMULATION_CURRENT_A = 0.012345  # ~12 mA, typical RFEB bias
_EMULATION_VOLTAGE_V = 1.234     # ~1.23 V, typical low-side rail


class DMMKeysight34461A(SCPIInstrument):
    """Keysight 34461A 6½-digit benchtop DMM driver."""

    _IDN_HINT = "Keysight Technologies,34461A,EMU0,A.00.00-EMU"

    def __init__(self, resource: str = "", *, is_emulation: bool = False) -> None:
        super().__init__(resource, is_emulation=is_emulation)
        # Track current mode so set_range_* can dispatch to the right
        # SCPI form and so get_measurement() can pick a sensible canned
        # value in emulation.
        self._mode: str | None = None  # "CURR" or "VOLT"

    # --- EVT-helper-facing API --------------------------------------------
    def set_mode(self, *, isVoltage: bool, isDc: bool) -> None:
        """Configure the DMM for DC current or DC voltage measurement.

        AC paths raise NotImplementedError until a real test needs them —
        no silent no-op.
        """
        if not isDc:
            raise NotImplementedError(
                "DMMKeysight34461A.set_mode: AC current / AC voltage modes "
                "are not implemented in V1f. Add CONF:CURR:AC / CONF:VOLT:AC "
                "handling when the first test that needs them migrates.")
        if isVoltage:
            self.write("CONFigure:VOLTage:DC AUTO")
            self._mode = "VOLT"
        else:
            self.write("CONFigure:CURRent:DC AUTO")
            self._mode = "CURR"

    def set_range_current(self, range_A: float) -> None:
        """Set the DC current range. Keysight 34461A: 0.1 / 1 / 3 / 10 A."""
        self.write(f"CONFigure:CURRent:DC {range_A:g}")
        self._mode = "CURR"

    def set_range_voltage(self, range_V: float) -> None:
        """Set the DC voltage range. Keysight 34461A: 0.1 / 1 / 10 / 100 / 1000 V."""
        self.write(f"CONFigure:VOLTage:DC {range_V:g}")
        self._mode = "VOLT"

    def get_measurement(self) -> float:
        """Trigger a measurement and return the reading as a float.

        Uses ``READ?`` which initiates a single measurement with the current
        CONFigure: settings and returns the result. Faster than INITiate +
        FETCh? for the one-shot pattern the EVT helpers use.
        """
        raw = self.query("READ?")
        try:
            return float(raw)
        except ValueError:
            self.log.warning("DMMKeysight34461A.get_measurement: "
                             "unparseable response %r", raw)
            return math.nan

    # --- Emulation override -----------------------------------------------
    def _emulated_response(self, scpi: str) -> str:
        """Return canned values for the DMM-specific queries."""
        if scpi == "READ?":
            value = (_EMULATION_VOLTAGE_V if self._mode == "VOLT"
                     else _EMULATION_CURRENT_A)
            return f"{value:.6E}"
        return super()._emulated_response(scpi)
