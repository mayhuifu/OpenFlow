"""Shared SCPI-over-VISA instrument base class.

Extracted from the V1f Keysight 34461A DMM driver. Concrete instrument
drivers (SG, SA, WFG, refactored DMM) inherit this base and only add
their instrument-specific high-level methods on top of
``self.write`` / ``self.query``.

The base owns:

* The pyvisa session lifecycle (lazy import; clean RuntimeError if
  pyvisa isn't installed).
* The ``is_emulation`` mode with SCPI-command recording in
  ``self._scpi_log`` (engineers debug bench protocol without a logic
  analyzer).
* The ``_emulated_response()`` dispatch hook so subclasses can return
  canned values for the queries they care about.
* The standard ``identify()`` (``*IDN?``) and ``drain_errors()``
  (``SYSTem:ERRor?`` loop) helpers.

Subclasses override:

* ``_IDN_HINT`` — the canned response to ``*IDN?`` in emulation mode.
* ``_emulated_response()`` — optionally, to return canned values for
  instrument-specific queries (e.g. ``READ?`` on a DMM).
"""
from __future__ import annotations

import logging
from typing import Any

from openflow.instruments.base import Instrument

# pyvisa is an optional dependency — the V1a CI environment installs it via
# `uv sync` (declared in pyproject.toml runtime deps), but emulation users
# can install OpenFlow without it. We probe at module import so tests can
# monkeypatch the symbol to simulate the missing-dep path.
try:
    import pyvisa
except ImportError:  # pragma: no cover - exercised by monkeypatch test
    pyvisa = None  # type: ignore[assignment]


class SCPIInstrument(Instrument):
    """SCPI-over-VISA instrument base.

    Constructed with a VISA resource string (``TCPIP0::<host>::INSTR`` for
    LAN, ``USB0::...`` for USB) and an optional ``is_emulation`` flag
    for hardware-free tests.
    """

    # Subclasses MUST override with their actual vendor/model IDN.
    _IDN_HINT: str = "Unknown,SCPI,EMU0,0.0"

    # Default pyvisa session timeout in milliseconds.
    _DEFAULT_TIMEOUT_MS: int = 5_000

    def __init__(self, resource: str = "", *, is_emulation: bool = False) -> None:
        super().__init__(resource)
        self.log = logging.getLogger(type(self).__module__)
        self.is_emulation = is_emulation

        # Real-hardware path state — populated by open().
        self._rm: Any = None
        self._session: Any = None

        # Recorded SCPI traffic; useful for tests and for engineers
        # debugging command sequencing without a logic analyzer.
        self._scpi_log: list[str] = []

    # --- Instrument ABC ----------------------------------------------------
    def open(self) -> None:
        if self.is_emulation:
            self.log.info("%s: opening in emulation mode (resource=%r ignored)",
                          type(self).__name__, self.resource)
            self._session = None
            return
        if pyvisa is None:
            raise RuntimeError(
                f"{type(self).__name__}: pyvisa is not installed but is "
                "required for real-hardware operation. Either install it "
                "(`uv add pyvisa pyvisa-py`) or construct the driver with "
                "is_emulation=True for offline / CI runs.")
        if not self.resource:
            raise RuntimeError(
                f"{type(self).__name__}: real-hardware mode requires a VISA "
                "resource string (e.g. 'TCPIP0::192.168.1.50::INSTR'). "
                "Pass one via the constructor or the YAML config.")
        self.log.info("%s: opening %s", type(self).__name__, self.resource)
        self._rm = pyvisa.ResourceManager()
        self._session = self._rm.open_resource(self.resource)
        self._session.timeout = self._DEFAULT_TIMEOUT_MS

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception as exc:
                self.log.warning("%s: session close raised %s",
                                 type(self).__name__, exc)
            self._session = None
        if self._rm is not None:
            try:
                self._rm.close()
            except Exception as exc:
                self.log.warning("%s: ResourceManager close raised %s",
                                 type(self).__name__, exc)
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

    # --- Identity ---------------------------------------------------------
    def identify(self) -> str:
        """Return the response to ``*IDN?``."""
        if self.is_emulation:
            return self._IDN_HINT
        return self.query("*IDN?")

    def drain_errors(self, max_iters: int = 20) -> list[str]:
        """Drain the SCPI error queue. Returns the list of non-empty errors.

        Empty list means the queue was clean (the instrument returned
        ``0,"No error"`` immediately).
        """
        errs: list[str] = []
        for _ in range(max_iters):
            err = self.query("SYSTem:ERRor?")
            if err.startswith("0,") or err.startswith("+0,") or '"No error"' in err:
                break
            errs.append(err)
        return errs

    # --- Emulation helpers ------------------------------------------------
    def _emulated_response(self, scpi: str) -> str:
        """Return a plausible canned response for an emulation-mode query.

        Subclasses override to handle their instrument-specific queries.
        The base handles only ``*IDN?`` and ``SYSTem:ERRor?``.
        """
        if scpi == "*IDN?":
            return self._IDN_HINT
        if scpi == "SYSTem:ERRor?":
            return '0,"No error"'
        # Catch-all: empty string mimics an instrument that received an
        # unrecognized query.
        return ""
