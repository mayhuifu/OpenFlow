"""CMW100 façade — combines analyzer + generator mixins via composition.
Tests exercise the is_emulation=True path; real hardware in V1b."""
import pytest

from openflow.instruments.base import Instrument
from openflow.instruments.cmw100 import CMW100


def test_cmw100_is_instrument_subclass():
    assert issubclass(CMW100, Instrument)


def test_construction_with_is_emulation_propagates_to_mixins():
    cmw = CMW100("TCPIP::1::INSTR", is_emulation=True)
    assert cmw.is_emulation is True
    assert cmw.cmwa.is_emulation is True
    assert cmw.cmwg.is_emulation is True


def test_open_then_close_in_emulation_does_not_raise():
    cmw = CMW100("MOCK", is_emulation=True)
    cmw.open()
    cmw.close()


def test_meas_NrTxEVM_round_trip_in_emulation():
    cmw = CMW100("MOCK", is_emulation=True)
    cmw.open()
    cmw.setup_NrTx(
        in_band="n78", in_freq_pll_Hz=3_600_000_000, in_rfbw_Hz=100_000_000,
        in_rb_centre_freq_Hz=3_600_000_000, in_tx_power_dBm=0.0,
        in_tx_power_backoff_dB=5.0, in_modulation="16QAM",
        in_rf_connector=1, in_scs_Hz=30_000)
    cmw.meas_NrTxAll()
    evm = cmw.meas_NrTxEVM(use_cached=True)
    assert isinstance(evm, float)
    assert 2.0 <= evm < 3.0


def test_meas_NrTxPower_in_emulation():
    cmw = CMW100("MOCK", is_emulation=True)
    cmw.open()
    p = cmw.meas_NrTxPower(use_cached=False)
    assert isinstance(p, float)
    assert 23.0 <= p < 24.0


def test_set_arb_signal_rf_in_emulation_returns_None():
    cmw = CMW100("MOCK", is_emulation=True)
    cmw.open()
    assert cmw.set_arb_signal_rf(
        signal_type="5G", signal_option="16QAM",
        frequency_Hz=3.6e9, bw_Hz=100e6,
        power_level=-20, rf_connector_active=1) is None


def test_set_rf_power_in_emulation_returns_None():
    cmw = CMW100("MOCK", is_emulation=True)
    cmw.open()
    assert cmw.set_rf_power(-25.0) is None


def test_write_query_raises_NotImplementedError():
    # CMW100 uses R&S SDK; raw SCPI is not supported.
    cmw = CMW100("MOCK", is_emulation=True)
    with pytest.raises(NotImplementedError):
        cmw.write("*RST")
    with pytest.raises(NotImplementedError):
        cmw.query("*IDN?")
