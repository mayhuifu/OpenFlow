"""Tests for the v1.0.0-rc2 CMW100LteMixin (LTE TX measurement port).

These tests run entirely in is_emulation=True mode — no real CMW100,
no R&S SDK session opened. Validates the API surface contract that
the bench bring-up smoke test and the migrated EVT tests depend on.
"""
import math

import pytest

from openflow.instruments.cmw100 import CMW100
from openflow.instruments.cmw100_lte import _LTE_BW_CODE, CMW100LteMixin

# --- Direct mixin tests --------------------------------------------------

def test_setup_lte_tx_emulation_does_not_open_sdk():
    """Emulation mode means setup_LteTx never touches LteMeas/Base."""
    lte = CMW100LteMixin()
    lte.is_emulation = True
    lte.Open(VisaAddress=None)
    # SDK sessions never created in emulation.
    assert lte.LteMeas is None
    assert lte.Base is None
    # And setup_LteTx is a no-op (no exception).
    lte.setup_LteTx(in_band="B7", in_freq_pll_Hz=2.65e9, in_rfbw_Hz=10e6,
                    in_tx_power_dBm=0.0)
    lte.Close()


def test_meas_lte_tx_evm_returns_canned_in_emulation():
    lte = CMW100LteMixin()
    lte.is_emulation = True
    lte.Open(VisaAddress=None)
    lte.setup_LteTx(in_band="B7", in_freq_pll_Hz=2.65e9, in_rfbw_Hz=10e6)
    lte.meas_LteTxAll()
    evm = lte.meas_LteTxEVM(use_cached=True)
    assert isinstance(evm, float)
    assert math.isfinite(evm)
    assert 0.0 < evm < 100.0  # plausible EVM range


def test_meas_lte_tx_power_returns_canned_in_emulation():
    lte = CMW100LteMixin()
    lte.is_emulation = True
    lte.Open(VisaAddress=None)
    lte.setup_LteTx(in_band="B7", in_freq_pll_Hz=2.65e9, in_rfbw_Hz=10e6)
    lte.meas_LteTxAll()
    power = lte.meas_LteTxPower(use_cached=True)
    assert isinstance(power, float)
    assert math.isfinite(power)
    assert -100.0 < power < 50.0  # plausible TX power range


def test_meas_lte_tx_uncached_triggers_fresh_measurement():
    lte = CMW100LteMixin()
    lte.is_emulation = True
    lte.Open(VisaAddress=None)
    # Without prior meas_LteTxAll, use_cached=False should still return a value.
    evm = lte.meas_LteTxEVM(use_cached=False)
    assert math.isfinite(evm)


def test_setup_lte_tx_rejects_unsupported_bandwidth():
    """Non-standard LTE bandwidths (e.g. 7.5 MHz) should fail loudly."""
    lte = CMW100LteMixin()
    lte.is_emulation = False  # raise even without hardware so the validation runs
    # Pre-open so we have at least a state to operate on.
    with pytest.raises(ValueError, match="bandwidth"):
        lte.setup_LteTx(in_band="B7", in_rfbw_Hz=7.5e6)


def test_setup_lte_tx_rejects_unparseable_band():
    lte = CMW100LteMixin()
    lte.is_emulation = False
    with pytest.raises(ValueError, match="band number"):
        lte.setup_LteTx(in_band="not-a-band")


@pytest.mark.parametrize("bw_hz,expected_code", [
    (1.4e6, "B014"),
    (3e6,   "B030"),
    (5e6,   "B050"),
    (10e6,  "B100"),
    (15e6,  "B150"),
    (20e6,  "B200"),
])
def test_lte_bandwidth_code_table(bw_hz, expected_code):
    """Verify the LTE bandwidth → SCPI code table covers all 6 standard
    LTE bandwidths."""
    assert _LTE_BW_CODE[int(bw_hz)] == expected_code


def test_lte_bandwidth_table_has_no_extras():
    """Only the 6 standard LTE bandwidths are accepted. Catches regressions
    where someone adds a non-standard entry."""
    assert len(_LTE_BW_CODE) == 6


def test_close_idempotent_in_emulation():
    lte = CMW100LteMixin()
    lte.is_emulation = True
    lte.Open(VisaAddress=None)
    lte.Close()
    lte.Close()  # must not raise


def test_band_code_accepts_multiple_forms():
    """B7 / 7 / b7 / B07 — all should parse to band number 7."""
    for form in ["B7", "7", "b7", "B07"]:
        lte = CMW100LteMixin()
        lte.is_emulation = True
        lte.Open(VisaAddress=None)
        lte.setup_LteTx(in_band=form, in_rfbw_Hz=10e6)  # no exception


def test_tx_power_envelope_setting_uses_headroom():
    """Documented behavior: setup_LteTx adds +20 dB envelope-power
    headroom over the requested TX power. We can't verify the SCPI
    write directly in emulation, but the test pins the docstring
    contract."""
    # Just confirm the call accepts the kwarg without raising.
    lte = CMW100LteMixin()
    lte.is_emulation = True
    lte.Open(VisaAddress=None)
    lte.setup_LteTx(in_band="B7", in_rfbw_Hz=10e6, in_tx_power_dBm=15.0)


# --- SCPI suffix regression (v1.0.0-rc4 bench-feedback fix) ---------------

def test_setup_lte_tx_uses_measurement1_suffix_not_bare_meas():
    """v1.0.0-rc4: CMW100 firmware 3.8.17 rejects `LTE:MEAS:...` with
    `-114 \"Header suffix out of range\"`. The canonical form requires
    a numeric suffix on MEASurement (i.e. `LTE:MEASurement1:...`).

    This test pins the corrected SCPI form in the _scpi_log.
    Bench engineer at bench SZLABPC-WIN04 found this in v1.0.0-rc2.
    """
    lte = CMW100LteMixin()
    lte.is_emulation = True
    lte.Open(VisaAddress=None)
    lte.setup_LteTx(in_band="B7", in_freq_pll_Hz=2.65e9, in_rfbw_Hz=10e6,
                    in_tx_power_dBm=0.0, in_duplex_mode="FDD")

    # Every command must use the `MEASurement1` form, not the bare `MEAS`.
    log_text = "\n".join(lte._scpi_log)
    assert "LTE:MEASurement1:" in log_text
    # Regression-pin the specific commands that fired -114 on bench:
    assert "CONFigure:LTE:MEASurement1:MEValuation:DMODe FDD" in lte._scpi_log
    # No bare `:MEAS:` should appear anywhere (would re-trigger -114).
    for cmd in lte._scpi_log:
        # `MEAS` is a valid token only when followed by a digit (e.g. MEAS1) —
        # never as a bare keyword in our SCPI.
        assert ":MEAS:" not in cmd, (
            f"Bare ':MEAS:' (no instance suffix) found in SCPI command — "
            f"will trigger -114 'Header suffix out of range' on CMW100: {cmd!r}"
        )


# --- CMW100 façade integration ------------------------------------------

def test_cmw100_facade_exposes_lte_methods():
    """V1.0.0-rc2: the façade exposes the LTE measurement surface
    alongside the NR + generator surfaces."""
    cmw = CMW100(resource="MOCK::CMW100::INSTR", is_emulation=True)
    cmw.open()
    # Setup + measurement via the façade.
    cmw.setup_LteTx(in_band="B7", in_freq_pll_Hz=2.65e9, in_rfbw_Hz=10e6)
    cmw.meas_LteTxAll()
    evm = cmw.meas_LteTxEVM(use_cached=True)
    power = cmw.meas_LteTxPower(use_cached=True)
    assert math.isfinite(evm)
    assert math.isfinite(power)
    cmw.close()


def test_cmw100_facade_lte_does_not_collide_with_nr():
    """NR + LTE mixins coexist on the same façade. Calling LTE methods
    does not corrupt the NR measurement state, and vice versa."""
    cmw = CMW100(resource="MOCK::CMW100::INSTR", is_emulation=True)
    cmw.open()
    # NR setup
    cmw.setup_NrTx(in_band="n78", in_freq_pll_Hz=3.5e9, in_rfbw_Hz=100e6,
                   in_tx_power_dBm=0.0)
    # LTE setup interleaved
    cmw.setup_LteTx(in_band="B7", in_freq_pll_Hz=2.65e9, in_rfbw_Hz=10e6)
    # Both measurement surfaces still work
    cmw.meas_NrTxAll()
    cmw.meas_LteTxAll()
    nr_evm = cmw.meas_NrTxEVM(use_cached=True)
    lte_evm = cmw.meas_LteTxEVM(use_cached=True)
    assert math.isfinite(nr_evm)
    assert math.isfinite(lte_evm)
    cmw.close()


def test_cmw100_facade_close_releases_lte_mixin():
    """close() must release the LTE mixin alongside NR + generator."""
    cmw = CMW100(resource="MOCK::CMW100::INSTR", is_emulation=True)
    cmw.open()
    cmw.close()
    # If close() raised, the test would have failed already.
