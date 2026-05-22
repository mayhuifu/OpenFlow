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

Plus the standard ``Instrument`` ABC contract (``open`` / ``close`` /
``write`` / ``query`` / ``identify``).

The ``is_emulation=True`` mode is the V1-style hardware-free path:

* No pyvisa import or session — the driver records each SCPI command into
  ``self._scpi_log`` for inspection / test assertions.
* ``get_measurement()`` returns a deterministic-but-plausible canned value
  so end-to-end EVT-helper exercises run cleanly without a bench.

On the real-hardware path (``is_emulation=False``) the driver imports pyvisa
lazily at ``open()`` time. If pyvisa is absent it raises a single, readable
``RuntimeError`` pointing the engineer at the install step rather than failing
mid-test with a confusing ImportError.
"""
from __future__ import annotations

import logging
from typing import Any

from openflow.instruments.base import Instrument

# pyvisa is an optional dependency — the V1a CI environment installs it via
# `uv sync` (declared in pyproject.toml `dependency-groups.dev`), but emulation
# users can install OpenFlow without it. We probe at module import so tests can
# monkeypatch the symbol to simulate the missing-dep path.
try:
    import pyvisa
except ImportError:  # pragma: no cover - exercised by monkeypatch test
    pyvisa = None  # type: ignore[assignment]


# Canned emulation reading. Deterministic so test assertions are stable;
# plausible enough that downstream consumers don't mistake it for an error
# sentinel.
_EMULATION_CURRENT_A = 0.012345  # ~12 mA, typical RFEB bias
_EMULATION_VOLTAGE_V = 1.234     # ~1.23 V, typical low-side rail


class DMMKeysight34461A(Instrument):
    """Keysight 34461A 6½-digit benchtop DMM driver.

    Constructed with a VISA resource string (``TCPIP0::<host>::INSTR`` for
    LAN, ``USB0::...`` for USB, etc.) and an optional ``is_emulation`` flag
    for hardware-free tests.
    """

    _IDN_HINT = "Keysight Technologies,34461A,EMU0,A.00.00-EMU"

    def __init__(self, resource: str = "", *, is_emulation: bool = False) -> None:
        super().__init__(resource)
        self.log = logging.getLogger(__name__)
        self.is_emulation = is_emulation

        # Real-hardware path state — populated by open().
        self._rm: Any = None
        self._session: Any = None

        # Recorded SCPI traffic; useful for tests and for engineers
        # debugging command sequencing without a logic analyzer.
        self._scpi_log: list[str] = []

        # Track current mode so set_range_* can dispatch to the right
        # SCPI form and so get_measurement() can pick a sensible canned
        # value in emulation.
        self._mode: str | None = None  # "CURR" or "VOLT"

    # --- Instrument ABC ----------------------------------------------------
    def open(self) -> None:
        if self.is_emulation:
            self.log.info("DMMKeysight34461A: opening in emulation mode "
                          "(resource=%r ignored)", self.resource)
            self._session = None
            return
        if pyvisa is None:
            raise RuntimeError(
                "DMMKeysight34461A: pyvisa is not installed but is required "
                "for real-hardware operation. Either install it "
                "(`uv add pyvisa pyvisa-py`) or construct the driver with "
                "is_emulation=True for offline / CI runs.")
        if not self.resource:
            raise RuntimeError(
                "DMMKeysight34461A: real-hardware mode requires a VISA "
                "resource string (e.g. 'TCPIP0::192.168.1.50::INSTR'). "
                "Pass one via the constructor or the YAML config.")
        self.log.info("DMMKeysight34461A: opening %s", self.resource)
        self._rm = pyvisa.ResourceManager()
        self._session = self._rm.open_resource(self.resource)
        # Conservative timeout — DMM queries should be sub-second.
        self._session.timeout = 5_000

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception as exc:  # best-effort cleanup
                self.log.warning("DMMKeysight34461A: session close raised %s", exc)
            self._session = None
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception as exc:
                self.log.warning("DMMKeysight34461A: ResourceManager close "
                                 "raised %s", exc)
            self._rm = None

    def write(self, scpi: str) -> None:
        """Send a SCPI command. Records into ``_scpi_log`` either way."""
        self._scpi_log.append(scpi)
        if self.is_emulation:
            return
        assert self._session is not None, "open() must be called before write()"
        self._session.write(scpi)

    def query(self, scpi: str) -> str:
        """Send a SCPI query. Records into ``_scpi_log`` either way."""
        self._scpi_log.append(scpi)
        if self.is_emulation:
            return self._emulated_response(scpi)
        assert self._session is not None, "open() must be called before query()"
        result: str = self._session.query(scpi)
        return result.strip()

    # --- Identity ----------------------------------------------------------
    def identify(self) -> str:
        if self.is_emulation:
            return self._IDN_HINT
        return self.query("*IDN?")

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
            import math
            return math.nan

    # --- Emulation helpers -------------------------------------------------
    def _emulated_response(self, scpi: str) -> str:
        """Return a plausible canned response for an emulation-mode query."""
        if scpi == "*IDN?":
            return self._IDN_HINT
        if scpi == "READ?":
            value = (_EMULATION_VOLTAGE_V if self._mode == "VOLT"
                     else _EMULATION_CURRENT_A)
            return f"{value:.6E}"
        # Catch-all: empty string mimics a DMM that received an unrecognized
        # query (the engineer will see this in _scpi_log).
        return ""
