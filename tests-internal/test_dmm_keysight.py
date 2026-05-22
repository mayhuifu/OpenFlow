"""Tests for the Keysight 34461A SCPI DMM driver.

Tests run entirely in `is_emulation=True` mode — no pyvisa required at
test time, no real bench. The driver records every SCPI command sent
to ``self._scpi_log`` so we can assert protocol-correctness without
mocking pyvisa.

The Keysight 34461A SCPI surface used by ``setup_dmm`` / ``get_dmm`` is:

    CONFigure:CURRent:DC <range>     (DC current measurement + range)
    CONFigure:VOLTage:DC <range>     (DC voltage measurement + range)
    READ?                            (trigger + return result)

Each driver method maps to one or more of those commands.
"""
import math

import pytest

from openflow.instruments.dmm_keysight import DMMKeysight34461A


def test_emulation_mode_does_not_require_pyvisa():
    """Constructing + opening in emulation must not import or call pyvisa."""
    dmm = DMMKeysight34461A(resource="TCPIP::dummy::INSTR", is_emulation=True)
    dmm.open()
    # Emulation path never opens a real session.
    assert dmm._session is None
    dmm.close()


def test_idn_in_emulation_returns_canned_string():
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm.open()
    idn = dmm.identify()
    assert "Keysight" in idn or "Agilent" in idn
    assert "34461" in idn
    dmm.close()


def test_set_mode_dc_current_emits_conf_curr_dc():
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm.open()
    dmm.set_mode(isVoltage=False, isDc=True)
    assert any("CURRent:DC" in s or "CURR:DC" in s for s in dmm._scpi_log)
    dmm.close()


def test_set_mode_dc_voltage_emits_conf_volt_dc():
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm.open()
    dmm.set_mode(isVoltage=True, isDc=True)
    assert any("VOLTage:DC" in s or "VOLT:DC" in s for s in dmm._scpi_log)
    dmm.close()


def test_set_mode_rejects_ac_modes_until_supported():
    """We only need DC for the EVT helpers. AC paths should fail loudly
    until someone needs them, not silently no-op."""
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm.open()
    with pytest.raises(NotImplementedError):
        dmm.set_mode(isVoltage=False, isDc=False)  # DC=False = AC current
    dmm.close()


def test_set_range_current_emits_scpi_with_range_value():
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm.open()
    dmm.set_mode(isVoltage=False, isDc=True)
    dmm.set_range_current(10.0)
    # The full configuration line should reference the 10 A range.
    assert any("10" in s and ("CURR" in s or "RANGe" in s) for s in dmm._scpi_log)
    dmm.close()


def test_get_measurement_in_emulation_returns_finite_value():
    """Emulation mode should produce a plausible (non-NaN, finite) reading
    so EVT helpers can be exercised end-to-end without real hardware."""
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm.open()
    dmm.set_mode(isVoltage=False, isDc=True)
    dmm.set_range_current(1.0)
    reading = dmm.get_measurement()
    assert isinstance(reading, float)
    assert math.isfinite(reading)
    dmm.close()


def test_get_measurement_emits_read_query():
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm.open()
    dmm.set_mode(isVoltage=False, isDc=True)
    dmm.get_measurement()
    assert any("READ?" in s for s in dmm._scpi_log)
    dmm.close()


def test_context_manager_opens_and_closes():
    dmm = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    with dmm as d:
        assert d is dmm
        d.set_mode(isVoltage=False, isDc=True)
        d.set_range_current(0.1)
        reading = d.get_measurement()
        assert math.isfinite(reading)
    # close() ran; subsequent measurements should fail clearly.


def test_open_without_pyvisa_on_real_path_raises_clearly(monkeypatch):
    """If is_emulation=False but pyvisa isn't installed, the failure must
    be a single readable error pointing the engineer at the install step."""
    import openflow.instruments.dmm_keysight as mod
    monkeypatch.setattr(mod, "pyvisa", None)
    dmm = DMMKeysight34461A(resource="TCPIP::1.2.3.4::INSTR", is_emulation=False)
    with pytest.raises(RuntimeError, match="pyvisa"):
        dmm.open()


def test_works_against_evt_helpers_setup_dmm():
    """End-to-end smoke against the EVT helpers — confirms the driver's
    set_mode + set_range_current shape matches what setup_dmm calls."""
    from openflow.rfengine.evt_base import setup_dmm

    dmm_c = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm_c.open()
    # setup_dmm should drive the DMM to DC current at the 10 A range
    # (per the _DMM_RANGES_A table in evt_base).
    setup_dmm(dmms={"dmm_c": dmm_c})
    # At minimum we should have seen a DC-current configuration.
    assert any("CURR" in s for s in dmm_c._scpi_log)
    dmm_c.close()


def test_works_against_evt_helpers_get_dmm():
    """End-to-end smoke against get_dmm — confirms the driver's
    get_measurement() returns a float and ends up in the out_*_A dict."""
    from openflow.rfengine.evt_base import get_dmm, setup_dmm

    dmm_c = DMMKeysight34461A(resource="MOCK::", is_emulation=True)
    dmm_c.open()
    setup_dmm(dmms={"dmm_c": dmm_c})
    readings = get_dmm(dmms={"dmm_c": dmm_c})
    assert "out_ibat_A" in readings
    assert math.isfinite(readings["out_ibat_A"])
    dmm_c.close()
