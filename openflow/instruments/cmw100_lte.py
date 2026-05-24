"""CMW100LteMixin — LTE TX measurement methods for the R&S CMW100.

Sibling to ``CMW100AMixin`` (NR FR1 Meas). The split exists because:

- A CMW100 may be licensed for LTE Meas (option KM500) but NOT for NR FR1 Meas
  — that's exactly the bench scenario discovered in v1.0.0-rc1 bring-up
  (CMW100 serial 131694: KM200/KM400/KM500, zero NR options).
- LTE and NR have separate ``RsCmwLteMeas`` / ``RsCmwNrFr1Meas`` SDK packages.
  Coupling them in one mixin makes the import-failure mode confusing — if
  ``RsCmwNrFr1Meas`` is missing the whole NR+LTE module fails to load.
  Splitting lets the LTE path stay importable on NR-less benches.

API mirror to ``CMW100AMixin`` (NR FR1):

    setup_LteTx(...)          ↔  setup_NrTx(...)
    meas_LteTxAll()           ↔  meas_NrTxAll()
    meas_LteTxEVM(...)        ↔  meas_NrTxEVM(...)
    meas_LteTxPower(...)      ↔  meas_NrTxPower(...)

The CMW100 façade (``openflow.instruments.cmw100``) exposes both surfaces;
engineers pick which one to call based on whether their bench is licensed
for NR or LTE (or both).

Scope notes:

- Ports the TX-EVM smoke subset only. Full LTE measurement surface
  (ACLR, SEM, In-Band Emissions, etc.) lands on demand as engineers
  migrate LTE EVT tests.
- Mirrors the V1a NR ``is_emulation`` pattern — emulation returns
  plausible canned values so CI runs hardware-free.
- Uses the ``RsCmwLteMeas`` SDK when available; falls back to raw SCPI
  via ``self.Base.utilities`` if the SDK API path differs.

LTE bandwidth → channel code table (CMW100 SCPI):
    1.4 MHz → B014
    3 MHz   → B030
    5 MHz   → B050
    10 MHz  → B100
    15 MHz  → B150
    20 MHz  → B200
"""
from __future__ import annotations

import logging
import math
import re
import time

# The R&S SDK packages — same import pattern as cmw100_a.py.
from RsCmwLteMeas import *

try:
    from RsCmwBase import *  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    try:
        from rscmw_base import RsCmwBase  # type: ignore[import-not-found]
    except ImportError:
        RsCmwBase = None  # type: ignore[assignment]


# LTE bandwidth code lookup. Maps RF bandwidth in Hz to the CMW100's
# SCPI bandwidth selector (B014 / B030 / B050 / B100 / B150 / B200).
_LTE_BW_CODE: dict[int, str] = {
    int(1.4e6):  "B014",
    int(3.0e6):  "B030",
    int(5.0e6):  "B050",
    int(10.0e6): "B100",
    int(15.0e6): "B150",
    int(20.0e6): "B200",
}

# Canned emulation readings — deterministic so tests are stable, plausible
# enough that downstream consumers don't mistake them for error sentinels.
_EMULATION_TX_POWER_DBM = -10.0
_EMULATION_EVM_PCT = 1.42


class CMW100LteMixin:
    """LTE TX measurement methods for the R&S CMW100.

    Lifecycle is managed by the CMW100 façade — ``Open`` is called once
    with the VISA resource string, then setup/measurement methods can
    be called as needed. ``Close`` releases the SDK sessions.
    """

    LteMeas = None
    Base = None
    VisaAddress = None
    is_emulation = False
    # Default RF input connector (R11). Overridable per-call.
    in_rf_connector: int = 1

    def __init__(self) -> None:
        self.log = logging.getLogger(__name__)
        self.delay_pre_measurement = 3
        self.delay_pre_fetch = 0.2
        # Cache of the last measured tuple — populated by meas_LteTxAll,
        # consumed by meas_LteTxEVM / meas_LteTxPower with use_cached=True.
        self._last_meas: dict[str, float] = {}
        # Recorded SCPI traffic — useful for bench-side post-mortem when
        # debugging a CMW100 SCPI error. Mirror of the V3 SCPIInstrument
        # base's _scpi_log; LTE doesn't inherit from that base because
        # the lifecycle is owned by the CMW100 façade, not pyvisa.
        self._scpi_log: list[str] = []

    # --- Lifecycle ---------------------------------------------------------

    def Open(self, VisaAddress: str | None) -> None:
        """Open the LTE Meas + Base SDK sessions."""
        if self.is_emulation:
            return
        self.VisaAddress = VisaAddress
        if VisaAddress is None:
            self.log.warning("CMW100LteMixin.Open: VisaAddress is None — "
                             "LTE measurements will not work")
            return
        self.LteMeas = RsCmwLteMeas(VisaAddress)
        if RsCmwBase is not None:
            self.Base = RsCmwBase(VisaAddress)

    def Close(self) -> None:
        if self.is_emulation:
            return
        if self.LteMeas is not None:
            try:
                self.LteMeas.close()
            except Exception as exc:
                self.log.warning("CMW100LteMixin: LteMeas close raised %s", exc)
        if self.Base is not None:
            try:
                self.Base.close()
            except Exception as exc:
                self.log.warning("CMW100LteMixin: Base close raised %s", exc)

    # --- Setup -------------------------------------------------------------

    def setup_LteTx(self, *, in_band: str = "B7", in_freq_pll_Hz: float = 2.65e9,
                    in_rfbw_Hz: float = 10e6, in_tx_power_dBm: float = 0.0,
                    in_modulation: str = "QPSK",
                    in_duplex_mode: str = "FDD",
                    in_rf_connector: int = 1) -> None:
        """Configure the CMW100 LTE measurement subsystem for a TX measurement.

        Args:
            in_band: LTE band code (e.g. "B7" for band 7). The leading 'B'
                is stripped — accept "B7" or "7" or "n7" (cosmetic).
            in_freq_pll_Hz: carrier frequency in Hz.
            in_rfbw_Hz: channel bandwidth in Hz (must be one of the 6
                standard LTE bandwidths).
            in_tx_power_dBm: expected DUT TX power for the envelope
                power setting (CMW adds +20 dB headroom).
            in_modulation: "QPSK" / "16QAM" / "64QAM" / "256QAM".
                Currently advisory — the LTE meas auto-detects modulation
                in MEValuation mode; the arg is preserved for parity
                with setup_NrTx and for future explicit-mode support.
            in_duplex_mode: "FDD" or "TDD".
            in_rf_connector: 1..8 → R11..R18 on the CMW100 front panel.
        """
        # Validate inputs UP-FRONT — these are user errors, raised
        # regardless of emulation mode or session state.
        m = re.search(r"\d+", str(in_band))
        if not m:
            raise ValueError(
                f"setup_LteTx: cannot parse band number from {in_band!r}")
        band_number = int(m.group())

        bw_code = _LTE_BW_CODE.get(int(in_rfbw_Hz))
        if bw_code is None:
            raise ValueError(
                f"setup_LteTx: unsupported LTE bandwidth {in_rfbw_Hz/1e6} MHz. "
                f"Must be one of {sorted(b / 1e6 for b in _LTE_BW_CODE)}.")

        if not self.is_emulation and self.LteMeas is None:
            self.log.warning("setup_LteTx: LteMeas session not open")
            return

        if self.is_emulation:
            self.log.info("CMW100LteMixin.setup_LteTx: emulation — "
                          "band=%s freq=%g Hz bw=%g Hz power=%g dBm",
                          in_band, in_freq_pll_Hz, in_rfbw_Hz, in_tx_power_dBm)

        # Best-effort: instantiate + select an LTE Meas application before
        # the configuration commands. This is required on CMW100 firmware
        # that uses the multi-app architecture (where measurement subtrees
        # are inaccessible until the matching app is selected). On older
        # firmware these commands fail with -113 / -114, which is tolerated.
        self._write_scpi_tolerant('INSTrument:CREate:NAME "LTE Meas 1", "LTE Meas"')
        self._write_scpi_tolerant('INSTrument:SELect "LTE Meas 1"')

        # Build the SCPI commands. We use raw write via the Base utilities
        # because the LTE SDK's enum surface varies subtly across SDK
        # versions and raw SCPI is stable + debuggable.
        #
        # The `MEASurement1` suffix is required — bench testing on CMW100
        # firmware 3.8.17 (v1.0.0-rc2) found that bare `LTE:MEAS:...` is
        # rejected with -114 "Header suffix out of range". The instance
        # number (1) selects the first LTE measurement instance.
        scpi_writes = [
            # Duplex mode.
            f"CONFigure:LTE:MEASurement1:MEValuation:DMODe {in_duplex_mode}",
            # Connector.
            f"ROUTe:LTE:MEASurement1:SCENario:SALone R1{in_rf_connector}",
            # RF settings — external attenuation, envelope power, user margin.
            "CONFigure:LTE:MEASurement1:RFSettings:EATTenuation 0",
            f"CONFigure:LTE:MEASurement1:RFSettings:ENPower {in_tx_power_dBm + 20.0:.2f}",
            "CONFigure:LTE:MEASurement1:RFSettings:UMARgin 0",
            # Band + frequency.
            f"CONFigure:LTE:MEASurement1:BAND OB{band_number}",
            f"CONFigure:LTE:MEASurement1:RFSettings:FREQuency {in_freq_pll_Hz:.0f}",
            # Channel bandwidth.
            f"CONFigure:LTE:MEASurement1:CBANDwidth {bw_code}",
            # MEValuation defaults — single-shot, all results.
            "CONFigure:LTE:MEASurement1:MEValuation:REPetition SINGleshot",
            "CONFigure:LTE:MEASurement1:MEValuation:MOEXception OFF",
        ]
        for cmd in scpi_writes:
            self._write_scpi(cmd)

        # Clear stale errors after configuration. Only sent on real
        # hardware — *CLS on a None Base is a no-op anyway, but skip
        # the trailing sleep to keep emulation-mode tests fast.
        if not self.is_emulation:
            self._write_scpi("*CLS")
            time.sleep(0.1)

    # --- Measurement -------------------------------------------------------

    def meas_LteTxAll(self) -> None:
        """Trigger one LTE MEValuation measurement cycle and cache results."""
        if self.is_emulation:
            self._last_meas = {
                "tx_power_dBm": _EMULATION_TX_POWER_DBM,
                "evm_pct": _EMULATION_EVM_PCT,
            }
            return

        if self.LteMeas is None:
            self.log.warning("meas_LteTxAll: LteMeas session not open")
            self._last_meas = {"tx_power_dBm": math.nan, "evm_pct": math.nan}
            return

        time.sleep(self.delay_pre_measurement)
        # Initiate single-shot measurement and wait.
        self._write_scpi("INITiate:LTE:MEASurement1:MEValuation")
        # Poll the measurement state until DONE (or timeout).
        for _ in range(60):  # ~30 s upper bound at 0.5 s polls
            state = self._query_scpi(
                "FETCh:LTE:MEASurement1:MEValuation:STATe?")
            if state and "RDY" in state.upper():
                break
            if state and "OFF" in state.upper():
                break
            time.sleep(0.5)

        time.sleep(self.delay_pre_fetch)

        # Modulation average — returns reliability + EVM/power/...
        # The exact field order in the response depends on SDK version;
        # parse defensively by index.
        try:
            mod_avg = self._query_scpi(
                "FETCh:LTE:MEASurement1:MEValuation:MODulation:AVERage?")
            parts = [p.strip() for p in (mod_avg or "").split(",")]
            # Typical order: <Reliability>, <OutOfTol>, <DMRS_Power>,
            # <EVMRms>, <EVMPeak>, <MERms>, <MEPeak>, <FreqErr>, <SampErr>,
            # <ChPower>, <ChPowerPeak>, <TxPower>, ...
            # We extract conservatively — EVMRms is index 3 in the
            # standard response, TxPower is later (commonly index 11).
            evm_pct = self._safe_float(parts, 3, math.nan)
            tx_power = self._safe_float(parts, 11, math.nan)
            self._last_meas = {"tx_power_dBm": tx_power, "evm_pct": evm_pct}
        except Exception as exc:
            self.log.warning("meas_LteTxAll: fetch failed (%s)", exc)
            self._last_meas = {"tx_power_dBm": math.nan, "evm_pct": math.nan}

    def meas_LteTxEVM(self, *, use_cached: bool = False) -> float:
        """Return the EVM RMS (in %) from the last measurement cycle.

        If ``use_cached`` is True, returns the value from the most-recent
        ``meas_LteTxAll`` call. Otherwise triggers a fresh measurement.
        """
        if not use_cached:
            self.meas_LteTxAll()
        return float(self._last_meas.get("evm_pct", math.nan))

    def meas_LteTxPower(self, *, use_cached: bool = False) -> float:
        """Return the measured TX power (in dBm) from the last cycle.

        If ``use_cached`` is True, returns the value from the most-recent
        ``meas_LteTxAll`` call. Otherwise triggers a fresh measurement.
        """
        if not use_cached:
            self.meas_LteTxAll()
        return float(self._last_meas.get("tx_power_dBm", math.nan))

    # --- internals --------------------------------------------------------

    def _write_scpi(self, cmd: str) -> None:
        """Send a raw SCPI command via the Base utilities. Records in
        ``_scpi_log`` regardless of emulation / session state so the
        log is a reliable post-mortem source even when the Base session
        isn't open yet (validation-only path)."""
        self._scpi_log.append(cmd)
        if self.Base is None:
            if not self.is_emulation:
                self.log.warning("_write_scpi: Base session not open — "
                                 "dropping %r", cmd)
            return
        self.Base.utilities.write_str(cmd)

    def _write_scpi_tolerant(self, cmd: str) -> bool:
        """Write a SCPI command; log + swallow any instrument error.

        Returns True on success, False on instrument-side rejection.
        Used for best-effort setup steps (e.g. INSTrument:CREate that
        might already exist) where we want to continue on error.
        """
        self._scpi_log.append(cmd)
        if self.Base is None:
            return self.is_emulation  # treat as "ok" in emulation
        try:
            self.Base.utilities.write_str(cmd)
            return True
        except Exception as exc:
            self.log.info("_write_scpi_tolerant: %r -> %s (continuing)", cmd, exc)
            # Clear the error queue so subsequent commands don't see this.
            try:
                self.Base.utilities.write_str("*CLS")
            except Exception:
                pass
            return False

    def _query_scpi(self, cmd: str) -> str | None:
        """Send a raw SCPI query via the Base utilities. Returns None
        if the Base session is closed."""
        self._scpi_log.append(cmd)
        if self.Base is None:
            return None
        result: str = self.Base.utilities.query_str(cmd)
        return result

    @staticmethod
    def _safe_float(parts: list[str], idx: int, default: float) -> float:
        """Defensively extract a float from a comma-split SCPI response."""
        if idx >= len(parts):
            return default
        try:
            return float(parts[idx])
        except (ValueError, TypeError):
            return default
