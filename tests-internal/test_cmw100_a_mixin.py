"""CMW100AMixin emulation-mode tests. Real-hardware paths covered in V1b."""
from openflow.instruments.cmw100_a import CMW100AMixin


def _make_emul_mixin() -> CMW100AMixin:
    m = CMW100AMixin()
    m.is_emulation = True
    return m


def test_emulation_open_does_not_raise():
    m = _make_emul_mixin()
    m.Open(VisaAddress=None)


def test_emulation_close_does_not_raise():
    m = _make_emul_mixin()
    m.Close()


def test_emulation_setup_NrTx_returns_None():
    m = _make_emul_mixin()
    result = m.setup_NrTx(
        in_band="n78",
        in_freq_pll_Hz=3_600_000_000,
        in_rfbw_Hz=100_000_000,
        in_rb_centre_freq_Hz=3_600_000_000,
        in_tx_power_dBm=0.0,
        in_tx_power_backoff_dB=5.0,
        in_modulation="16QAM",
        in_rf_connector=1,
        in_scs_Hz=30_000,
    )
    assert result is None


def test_emulation_meas_NrTxAll_returns_None():
    m = _make_emul_mixin()
    assert m.meas_NrTxAll() is None


def test_emulation_meas_NrTxEVM_returns_plausible_float():
    m = _make_emul_mixin()
    v = m.meas_NrTxEVM(use_cached=False)
    assert isinstance(v, float)
    assert 2.0 <= v < 3.0  # original CMW100A.py returns 2.0 + np.random.rand()


def test_emulation_meas_NrTxPower_returns_plausible_float():
    m = _make_emul_mixin()
    v = m.meas_NrTxPower(use_cached=False)
    assert isinstance(v, float)
    assert 23.0 <= v < 24.0  # original returns 23 + np.random.rand()


def test_attributes_initialized():
    m = _make_emul_mixin()
    assert m.is_emulation is True
    assert hasattr(m, "log")
    assert hasattr(m, "freq_start")
    assert hasattr(m, "freq_stop")
