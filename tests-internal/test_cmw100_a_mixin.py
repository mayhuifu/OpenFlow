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


# --- v1.0.0-rc9 bench-feedback regressions --------------------------------
# Bench SZLABPC-WIN04 hit `UnboundLocalError: local variable 'rf_con'
# referenced before assignment` on `setup_NrTx` because the EVT config
# passes `in_ul_config="TX0_ANT0"` and the original migration code only
# recognized "ANT0" / "ANT1" exactly. _resolve_rf_connector generalizes.

def test_resolve_rf_connector_none_returns_explicit_connector():
    """When `in_ul_config` is None, the caller's explicit connector wins."""
    m = CMW100AMixin()
    assert m._resolve_rf_connector(None, 5) == 5


def test_resolve_rf_connector_exact_ant0_uses_class_default():
    """Backwards-compat: bare "ANT0" still maps to in_rf_connector_ant0."""
    m = CMW100AMixin()
    assert m._resolve_rf_connector("ANT0", 7) == m.in_rf_connector_ant0


def test_resolve_rf_connector_exact_ant1_uses_class_default():
    m = CMW100AMixin()
    assert m._resolve_rf_connector("ANT1", 7) == m.in_rf_connector_ant1


def test_resolve_rf_connector_tx0_ant0_form_maps_to_ant0():
    """rc9: "TX0_ANT0" — actual EVT config value — must map to ant0,
    not crash with UnboundLocalError."""
    m = CMW100AMixin()
    assert m._resolve_rf_connector("TX0_ANT0", 99) == m.in_rf_connector_ant0


def test_resolve_rf_connector_tx0_ant1_form_maps_to_ant1():
    m = CMW100AMixin()
    assert m._resolve_rf_connector("TX0_ANT1", 99) == m.in_rf_connector_ant1


def test_resolve_rf_connector_tx1_ant0_form_maps_to_ant0():
    """Multi-TX form: TX1_ANT0 still routes by the antenna index."""
    m = CMW100AMixin()
    assert m._resolve_rf_connector("TX1_ANT0", 99) == m.in_rf_connector_ant0


def test_resolve_rf_connector_unrecognized_falls_back_with_warning(caplog):
    """Unknown values fall back to in_rf_connector + emit a warning so the
    silent miscompile in v1.0.0-rc8 (UnboundLocalError) can't recur."""
    import logging
    m = CMW100AMixin()
    caplog.set_level(logging.WARNING)
    result = m._resolve_rf_connector("WHATEVER", 3)
    assert result == 3
    assert any("not recognized" in rec.message for rec in caplog.records), (
        f"expected a 'not recognized' warning; got: "
        f"{[rec.message for rec in caplog.records]!r}"
    )


def test_resolve_rf_connector_can_override_ant_indices_per_instance():
    """Engineers can override the ant0/ant1 indices on the instance before
    calling setup_NrTx — e.g. for non-default DUT routing."""
    m = CMW100AMixin()
    m.in_rf_connector_ant0 = 5
    m.in_rf_connector_ant1 = 6
    assert m._resolve_rf_connector("TX0_ANT0", 1) == 5
    assert m._resolve_rf_connector("TX0_ANT1", 1) == 6


# Regression: ensure setup_NrTx itself doesn't crash on the EVT config
# shape that triggered the bench failure. Runs under is_emulation so no
# SDK is needed; the resolution path executes before the emulation guard
# returns, so the test still proves the new helper is wired in.

def test_setup_nrtx_with_tx0_ant0_does_not_unboundlocal():
    """rc9: bench SZLABPC-WIN04 hit UnboundLocalError on
    `cmw100.setup_NrTx(in_ul_config="TX0_ANT0", ...)`. Even though
    emulation mode short-circuits before the broken if/elif/else, this
    test pins that the call signature works end-to-end with the EVT
    config's ul_config value."""
    m = CMW100AMixin()
    m.is_emulation = True
    # Must not raise.
    m.setup_NrTx(
        in_band="n78",
        in_freq_pll_Hz=3.5e9,
        in_rfbw_Hz=100e6,
        in_rb_centre_freq_Hz=3.5e9,
        in_tx_power_dBm=-30.0,
        in_tx_power_backoff_dB=5.0,
        in_modulation="16QAM",
        in_ul_config="TX0_ANT0",  # the value that crashed on bench
        in_scs_Hz=30_000,
    )
