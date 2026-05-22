"""Placeholder instrument classes — real ports land in V2."""
import pytest

from openflow.instruments.base import Instrument
from openflow.instruments.stubs import DMM, OSC, PSU, SA, SG, WFG


@pytest.mark.parametrize("cls", [WFG, DMM, PSU, OSC, SG, SA])
def test_each_stub_is_subclass_of_Instrument(cls):
    assert issubclass(cls, Instrument)


@pytest.mark.parametrize("cls", [WFG, DMM, PSU, OSC, SG, SA])
def test_each_stub_instantiates_with_resource_arg(cls):
    inst = cls("TCPIP::1::INSTR")
    assert inst.resource == "TCPIP::1::INSTR"


@pytest.mark.parametrize("cls,name", [
    (WFG, "WFG"), (DMM, "DMM"), (PSU, "PSU"),
    (OSC, "OSC"), (SG, "SG"), (SA, "SA"),
])
def test_open_raises_NotImplementedError_naming_class_and_V2(cls, name):
    inst = cls("res")
    with pytest.raises(NotImplementedError) as exc:
        inst.open()
    msg = str(exc.value)
    assert name in msg
    assert "V2" in msg


@pytest.mark.parametrize("cls", [WFG, DMM, PSU, OSC, SG, SA])
def test_close_is_noop(cls):
    inst = cls("res")
    inst.close()  # must not raise
