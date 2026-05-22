"""DUT_U300 emulation-mode tests. Bench validation is V1b's manual step."""
import pytest

from openflow.dut.base import Dut
from openflow.dut.u300 import DUT_U300


def _make_emul_dut() -> DUT_U300:
    d = DUT_U300()
    d.emulation = True
    return d


def test_dut_u300_is_Dut_subclass():
    assert issubclass(DUT_U300, Dut)


def test_dut_u300_instantiation():
    d = _make_emul_dut()
    assert d.emulation is True


def test_get_BandNumber_returns_int():
    d = _make_emul_dut()
    assert d.get_BandNumber(band="n41") == 41
    assert d.get_BandNumber(band="n78") == 78


def test_dBm2dBV_conversion():
    d = _make_emul_dut()
    # Source formula: y = x + 10*log10(Z0) - 10*log10(1000) + 10*log10(2)
    # For x=0, Z0=50 → 16.99 - 30 + 3.01 ≈ -10.0 dBV
    v = d.dBm2dBV(x=0.0, Z0=50)
    assert isinstance(v, float)
    # Reasonable bound check — the exact value is about -10.0 dBV
    assert -12.0 < v < -8.0


def test_set_rfTxPower_emulation_returns_tuple():
    d = _make_emul_dut()
    result = d.set_rfTxPower(
        ul_powers_dBm=0.0,
        backoffs_dB=5.0,
        rb_centre_frequency_Hz=15e3,
        pll_frequency_Hz=2.5e9,
    )
    # Emulation returns (pwr, rfic_lut_idx, pa_lut_idx, dac_bo) as documented.
    assert isinstance(result, tuple)
    assert len(result) >= 4


def test_set_rfTxStop_emulation_does_not_raise():
    d = _make_emul_dut()
    d.set_rfTxStop()


def test_cmd_initialize_emulation_does_not_raise():
    d = _make_emul_dut()
    d.cmd_initialize()


def test_set_arb_signal_bb_emulation_does_not_raise():
    d = _make_emul_dut()
    d.set_arb_signal_bb(wfg=None, signal_type="5G", signal_option="QPSK")


def test_set_arb_power_dBFSrms_emulation_does_not_raise():
    d = _make_emul_dut()
    d.set_arb_power_dBFSrms(wfg=None, power_dBFSrms=-13.0)


def test_open_close_emulation_no_op():
    d = _make_emul_dut()
    d.Open()
    d.Close()


def test_unimplemented_methods_fall_through_to_Dut_getattr():
    d = _make_emul_dut()
    # Methods we did NOT port should hit Dut.__getattr__ and raise NotImplementedError.
    with pytest.raises(NotImplementedError) as exc:
        d.set_rfRxGain(45)  # not in V1b port
    assert "V1b" in str(exc.value)


# --- V1f audit: critical real-hardware methods must fail loudly on bench ---

def _make_bench_dut() -> DUT_U300:
    """A DUT_U300 with emulation explicitly OFF, to test the bench code path."""
    d = DUT_U300()
    d.emulation = False
    return d


def test_cmd_initialize_raises_on_bench_until_ported():
    """V1f: bench path must NOT silently warn-and-return — that masks the
    fact that init didn't actually happen. The engineer needs to see a
    clear failure with the port name."""
    d = _make_bench_dut()
    with pytest.raises(NotImplementedError) as exc:
        d.cmd_initialize()
    msg = str(exc.value)
    assert "cmd_initialize" in msg
    assert "rfd_simulator" in msg


def test_set_rfTxStop_raises_on_bench_until_ported():
    """V1f: same — silent no-op on bench would leave the DUT in an
    undefined Tx state at end-of-test."""
    d = _make_bench_dut()
    with pytest.raises(NotImplementedError) as exc:
        d.set_rfTxStop()
    msg = str(exc.value)
    assert "set_rfTxStop" in msg


def test_set_rfTxPower_raises_on_bench_until_ported():
    """V1f: critical — previously this returned canned values on bench
    which would silently produce wrong test data. Must fail loudly."""
    d = _make_bench_dut()
    with pytest.raises(NotImplementedError) as exc:
        d.set_rfTxPower(ul_powers_dBm=0.0, backoffs_dB=0.0,
                        rb_centre_frequency_Hz=15e3, pll_frequency_Hz=2.5e9)
    msg = str(exc.value)
    assert "set_rfTxPower" in msg
    assert "emulation" in msg.lower()  # message must point user at the workaround


def test_set_arb_signal_bb_silent_on_bench_is_faithful_to_source():
    """V1f: the source body was originally `pass` — silent on bench is
    faithful, not a bug. Keep the warning-only behavior."""
    d = _make_bench_dut()
    # Should NOT raise — original source was a no-op too.
    d.set_arb_signal_bb(wfg=None, signal_type="5G", signal_option="QPSK")


def test_set_arb_power_dBFSrms_silent_on_bench_is_faithful_to_source():
    """V1f: same as set_arb_signal_bb — original source was `pass`."""
    d = _make_bench_dut()
    d.set_arb_power_dBFSrms(wfg=None, power_dBFSrms=-13.0)
