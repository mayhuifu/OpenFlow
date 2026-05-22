"""Tests for the SCPIInstrument base class.

V3 extracts the pyvisa session + is_emulation SCPI-recording pattern
that the V1f DMM driver introduced ad-hoc into a reusable base.
Subclasses (SG, SA, WFG, refactored DMM) inherit open/close/write/query
+ identify + drain_errors and only add their instrument-specific
high-level methods.
"""
import pytest

from openflow.instruments.scpi import SCPIInstrument


class _ConcreteSCPI(SCPIInstrument):
    """Minimal concrete subclass for testing the base directly."""
    _IDN_HINT = "Test,Concrete,EMU0,0.0"


def test_emulation_mode_does_not_open_real_session():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    inst.open()
    assert inst._session is None
    inst.close()


def test_emulation_idn_returns_idn_hint():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    inst.open()
    assert inst.identify() == "Test,Concrete,EMU0,0.0"
    inst.close()


def test_write_records_in_scpi_log():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    inst.open()
    inst.write("FOO:BAR 1")
    inst.write("BAZ:QUX 2")
    assert inst._scpi_log == ["FOO:BAR 1", "BAZ:QUX 2"]
    inst.close()


def test_query_emulation_dispatches_to_emulated_response():
    class WithResponse(SCPIInstrument):
        _IDN_HINT = "X,Y,Z,0"

        def _emulated_response(self, scpi):
            if scpi == "READ?":
                return "1.234E-3"
            return super()._emulated_response(scpi)

    inst = WithResponse(resource="MOCK::", is_emulation=True)
    inst.open()
    assert inst.query("READ?") == "1.234E-3"
    assert inst.query("*IDN?") == "X,Y,Z,0"
    inst.close()


def test_drain_errors_in_emulation_returns_empty_list():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    inst.open()
    assert inst.drain_errors() == []
    inst.close()


def test_open_without_pyvisa_on_real_path_raises_clearly(monkeypatch):
    import openflow.instruments.scpi as mod
    monkeypatch.setattr(mod, "pyvisa", None)
    inst = _ConcreteSCPI(resource="TCPIP::1::INSTR", is_emulation=False)
    with pytest.raises(RuntimeError, match="pyvisa"):
        inst.open()


def test_open_without_resource_on_real_path_raises_clearly():
    inst = _ConcreteSCPI(resource="", is_emulation=False)
    with pytest.raises(RuntimeError, match="VISA resource"):
        inst.open()


def test_context_manager_opens_and_closes():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    with inst as i:
        i.write("FOO 1")
    assert inst._session is None  # close ran cleanly


def test_close_is_idempotent():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    inst.open()
    inst.close()
    inst.close()  # must not raise


def test_query_systemerror_returns_no_error_in_emulation():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    inst.open()
    response = inst.query("SYSTem:ERRor?")
    assert "No error" in response
    inst.close()


def test_unknown_query_returns_empty_string_in_emulation():
    inst = _ConcreteSCPI(resource="MOCK::", is_emulation=True)
    inst.open()
    # Unknown SCPI query — no canned response from base, no override.
    assert inst.query("UNKNOWN:QUERY?") == ""
    inst.close()
