"""Dut base — port of UMT_DUTs.UMT_DUT minus OpenTAP scaffolding.

V1a ships this base only; the real U300 subclass (DUT_U300.py) lands in V1b.
The __getattr__ fallback lets the migrated TX EVM test *collect* even though
it calls methods like set_rfTxPower that the real DUT will implement later.
"""
import logging

import pytest

from openflow.dut.base import Dut


def test_Dut_can_be_instantiated():
    dut = Dut()
    assert dut is not None


def test_emulation_defaults_to_False():
    dut = Dut()
    assert dut.emulation is False


def test_name_attribute_matches_class():
    dut = Dut()
    assert dut.name == "Dut"


def test_log_is_logger_instance():
    dut = Dut()
    assert isinstance(dut.log, logging.Logger)


def test_get_id_returns_placeholder_string():
    dut = Dut()
    assert dut.get_id() == "No_ID"


def test_open_close_do_not_raise():
    dut = Dut()
    dut.open()
    dut.close()


def test_unknown_method_raises_NotImplementedError_mentioning_V1b():
    dut = Dut()
    with pytest.raises(NotImplementedError) as exc:
        dut.set_rfTxPower(0.0, 5.0)
    msg = str(exc.value)
    assert "set_rfTxPower" in msg
    assert "V1b" in msg


def test_unknown_method_returns_callable_when_just_accessed():
    dut = Dut()
    method = dut.set_rfRxGain  # attribute access only, not called
    assert callable(method)


def test_subclass_name_is_reflected():
    class DUT_U300(Dut):
        pass
    sub = DUT_U300()
    assert sub.name == "DUT_U300"
