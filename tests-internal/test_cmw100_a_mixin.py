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


# --- v1.0.0-rc11 bench-feedback regression --------------------------------
# bench SZLABPC-WIN04 (firmware 3.8.17, rc10) hit:
#   AttributeError: 'CMW100AMixin' object has no attribute 'get_NrErrors'
#   openflow/instruments/cmw100_a.py:570
# inside meas_NrTxPower. The helper was referenced from meas_NrTxEVM
# (line 517) and meas_NrTxPower (line 570) but never ported from
# OpenTAP. rc11 ports it as a non-fatal SCPI error-queue drain.

def test_get_nr_errors_exists_as_attribute():
    """rc11: the bare AttributeError must never recur. Pin that
    get_NrErrors is callable on the class."""
    m = CMW100AMixin()
    assert callable(getattr(m, "get_NrErrors", None)), (
        "CMW100AMixin must expose get_NrErrors() — required by "
        "meas_NrTxEVM and meas_NrTxPower."
    )


def test_get_nr_errors_emulation_returns_empty_list():
    """In emulation mode, no real SCPI is sent — get_NrErrors returns []
    without touching self.Base."""
    m = CMW100AMixin()
    m.is_emulation = True
    result = m.get_NrErrors()
    assert result == []
    assert m.err_list == []


def test_get_nr_errors_no_base_session_returns_empty_list():
    """Defensive: if Base session isn't open (rare — would happen if
    Open() was never called), get_NrErrors returns [] not crashes."""
    m = CMW100AMixin()
    m.is_emulation = False
    m.Base = None
    result = m.get_NrErrors()
    assert result == []


def test_get_nr_errors_drains_until_no_error():
    """Simulate a real CMW100 with a few queued errors followed by a
    'No error' reply. get_NrErrors should drain until the queue is
    empty, return the list, and store it on self.err_list."""
    import types
    m = CMW100AMixin()
    m.is_emulation = False
    # Build a fake Base.utilities with a scripted SYSTem:ERRor? sequence.
    replies = iter([
        '-114,"Header suffix out of range;SOME CMD"',
        '-109,"Missing parameter;OTHER CMD"',
        '0,"No error"',
    ])
    fake = types.SimpleNamespace(
        utilities=types.SimpleNamespace(
            query_str=lambda cmd: next(replies),
        )
    )
    m.Base = fake  # type: ignore[assignment]

    result = m.get_NrErrors()
    assert len(result) == 2
    assert "-114" in result[0]
    assert "-109" in result[1]
    assert m.err_list == result  # stored on the instance


def test_get_nr_errors_handles_plus_zero_form():
    """Some R&S firmware vintages reply '+0,"No error"' instead of
    '0,"No error"'. Both must terminate the drain loop."""
    import types
    m = CMW100AMixin()
    m.is_emulation = False
    fake = types.SimpleNamespace(
        utilities=types.SimpleNamespace(query_str=lambda cmd: '+0,"No error"'),
    )
    m.Base = fake  # type: ignore[assignment]
    assert m.get_NrErrors() == []


def test_get_nr_errors_swallows_query_exception():
    """If SYSTem:ERRor? itself raises (e.g. VISA timeout), the helper
    must not propagate — its callers are mid-measurement and would
    otherwise lose the measurement they just took."""
    import types
    m = CMW100AMixin()
    m.is_emulation = False
    def raising_query(_cmd):
        raise RuntimeError("VISA timeout")
    fake = types.SimpleNamespace(
        utilities=types.SimpleNamespace(query_str=raising_query),
    )
    m.Base = fake  # type: ignore[assignment]
    # Must not raise.
    assert m.get_NrErrors() == []
