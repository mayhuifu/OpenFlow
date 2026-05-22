"""Placeholder instrument classes — V1a/V1f/V3 mixed.

After V3, only PSU and OSC remain as placeholder stubs. DMM (V1f) and
SG/SA/WFG (V3) are now real-driver aliases.
"""
import pytest

from openflow.instruments.base import Instrument
from openflow.instruments.dmm_keysight import DMMKeysight34461A
from openflow.instruments.sa_keysight_n9020b import KeysightN9020B
from openflow.instruments.sg_rs_smw200a import RsSmw200a
from openflow.instruments.stubs import DMM, OSC, PSU, SA, SG, WFG
from openflow.instruments.wfg_keysight_33500b import Keysight33500B


# Only PSU and OSC remain as placeholders after V3.
@pytest.mark.parametrize("cls", [PSU, OSC])
def test_each_stub_is_subclass_of_Instrument(cls):
    assert issubclass(cls, Instrument)


@pytest.mark.parametrize("cls", [PSU, OSC])
def test_each_stub_instantiates_with_resource_arg(cls):
    inst = cls("TCPIP::1::INSTR")
    assert inst.resource == "TCPIP::1::INSTR"


@pytest.mark.parametrize("cls,name", [(PSU, "PSU"), (OSC, "OSC")])
def test_open_raises_NotImplementedError_naming_class_and_V2(cls, name):
    inst = cls("res")
    with pytest.raises(NotImplementedError) as exc:
        inst.open()
    msg = str(exc.value)
    assert name in msg
    assert "V2" in msg


@pytest.mark.parametrize("cls", [PSU, OSC])
def test_close_is_noop(cls):
    inst = cls("res")
    inst.close()  # must not raise


def test_dmm_alias_points_at_real_keysight_driver():
    """V1f: ``DMM`` is a re-export of the real Keysight 34461A driver."""
    assert DMM is DMMKeysight34461A


def test_sg_alias_points_at_real_smw200a_driver():
    """V3: ``SG`` is a re-export of the real R&S SMW200A driver."""
    assert SG is RsSmw200a


def test_sa_alias_points_at_real_keysight_n9020b_driver():
    """V3: ``SA`` default alias is the Keysight N9020B (rs_fsw via
    instruments.sa.model: rs_fsw selects the R&S subclass)."""
    assert SA is KeysightN9020B


def test_wfg_alias_points_at_real_keysight_33500b_driver():
    """V3: ``WFG`` is a re-export of the real Keysight 33500B driver."""
    assert WFG is Keysight33500B
