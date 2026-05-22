"""CMW100GMixin emulation-mode tests. Real-hardware paths covered in V1b."""
from openflow.instruments.cmw100_g import CMW100GMixin


def _make_emul_mixin() -> CMW100GMixin:
    m = CMW100GMixin()
    m.is_emulation = True
    return m


def test_emulation_open_does_not_raise():
    m = _make_emul_mixin()
    m.Open(VisaAddress=None)


def test_emulation_close_does_not_raise():
    m = _make_emul_mixin()
    m.Close()


def test_emulation_set_arb_signal_rf_returns_None_silently():
    m = _make_emul_mixin()
    result = m.set_arb_signal_rf(
        signal_type="5G", signal_option="16QAM",
        frequency_Hz=3.6e9, bw_Hz=100e6,
        power_level=-20, rf_connector_active=1)
    assert result is None


def test_emulation_set_rf_power_returns_None_silently():
    m = _make_emul_mixin()
    result = m.set_rf_power(power_in_dBm=-25.0)
    assert result is None


def test_attributes_initialized():
    m = _make_emul_mixin()
    assert m.is_emulation is True
    assert hasattr(m, "log")
    assert hasattr(m, "freq_start")
    assert hasattr(m, "freq_stop")
