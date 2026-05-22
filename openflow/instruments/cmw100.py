"""R&S CMW100 façade — combines the analyzer (mixin A) and generator (mixin G).

Public class consumed by the `cmw100` pytest fixture. Composes the two mixins
ported from the existing UMT codebase. The `is_emulation` flag flows down so
both mixins behave consistently — when True, all measurements return canned
plausible values without touching the R&S SDK or hardware.
"""
from __future__ import annotations

import logging
from typing import Any

from openflow.instruments.base import Instrument
from openflow.instruments.cmw100_a import CMW100AMixin
from openflow.instruments.cmw100_g import CMW100GMixin


class CMW100(Instrument):
    """R&S CMW100 (NR + LTE + GPRF combined tester)."""

    def __init__(self, resource: str = "", *, is_emulation: bool = False) -> None:
        super().__init__(resource)
        self.log = logging.getLogger(__name__)
        self.is_emulation = is_emulation

        self.cmwa = CMW100AMixin()
        self.cmwa.is_emulation = is_emulation

        self.cmwg = CMW100GMixin()
        self.cmwg.is_emulation = is_emulation

        # in_synchronization_mode is referenced by CMW100AMixin.setup_NrTx on the
        # real-hardware path; provide the same default the OpenTAP wrapper used.
        self.cmwa.in_synchronization_mode = "Enhanced"

    # --- Instrument ABC ----------------------------------------------------
    def open(self) -> None:
        self.cmwa.Open(self.resource if self.resource else None)
        self.cmwg.Open(self.resource if self.resource else None)

    def close(self) -> None:
        self.cmwa.Close()
        self.cmwg.Close()

    def write(self, scpi: str) -> None:
        raise NotImplementedError(
            "CMW100 uses the R&S Python SDK; raw SCPI is not supported. "
            "Use the high-level methods (setup_NrTx, meas_NrTxEVM, etc.).")

    def query(self, scpi: str) -> str:
        raise NotImplementedError(
            "CMW100 uses the R&S Python SDK; raw SCPI is not supported. "
            "Use the high-level methods.")

    # --- NR Tx measurement surface (delegates to mixin A) ------------------
    def setup_NrTx(self, **kwargs: Any) -> None:
        return self.cmwa.setup_NrTx(**kwargs)

    def meas_NrTxAll(self) -> None:
        return self.cmwa.meas_NrTxAll()

    def meas_NrTxEVM(self, *, use_cached: bool = False) -> float:
        return self.cmwa.meas_NrTxEVM(use_cached=use_cached)

    def meas_NrTxPower(self, *, use_cached: bool = False) -> float:
        return self.cmwa.meas_NrTxPower(use_cached=use_cached)

    # --- Generator surface (delegates to mixin G) --------------------------
    def set_arb_signal_rf(self, **kwargs: Any) -> None:
        return self.cmwg.set_arb_signal_rf(**kwargs)

    def set_rf_power(self, power_in_dBm: float) -> None:
        return self.cmwg.set_rf_power(power_in_dBm=power_in_dBm)
