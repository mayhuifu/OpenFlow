"""DUT_FT2232h_V03 emulation-mode tests. Real-hardware paths covered by bench validation."""
from openflow.dut.ft2232h import DUT_FT2232h_V03, Register


def _make_emul_dut() -> DUT_FT2232h_V03:
    d = DUT_FT2232h_V03()
    d.emulation = True
    return d


def test_register_constants_present():
    from openflow.dut import ft2232h
    assert ft2232h.REG_ADRESS == "Address"
    assert ft2232h.REG_VALUE == "Value"
    assert ft2232h.REG_NAME == "Name"
    assert ft2232h.REG_FIELD_MODE == "Field_Mode"
    assert "RW" in ft2232h.REG_FIELD_MODE_READABLE
    assert "WO" in ft2232h.REG_FIELD_MODE_WRITEABLE


def test_register_export_dict():
    reg = Register(adr=10, val=100.0, name="MY_REG", field_mode="RW")
    d = reg.export_dict()
    assert d["Address"] == 10
    assert d["Value"] == 100
    assert d["Name"] == "MY_REG"
    assert d["Field_Mode"] == "RW"


def test_register_raises_on_bad_value_for_writeable_field():
    """Source uses `field_mode is REG_FIELD_MODE_WRITEABLE` (identity check),
    so the test must pass the module constant itself, not a literal list."""
    import pytest

    from openflow.dut.ft2232h import REG_FIELD_MODE_WRITEABLE
    with pytest.raises(ValueError):
        Register(adr=10, val=float("nan"), name="X", field_mode=REG_FIELD_MODE_WRITEABLE)


def test_dut_can_be_instantiated_in_emulation():
    d = _make_emul_dut()
    assert d.emulation is True


def test_dut_open_close_in_emulation_does_not_touch_hardware():
    """Source's Open() short-circuits in emulation but Close() does not (no guard
    in the verbatim source). We only assert Open()'s emulation behavior here;
    Close() in emulation is exercised separately when PSU stubs are wired in."""
    d = _make_emul_dut()
    d.Open()
    assert d.port is None
    assert d.ctrl is None


def test_dut_read_in_emulation_returns_emulation_value():
    """Source returns the `emulation_return` default (0x0000) in emulation mode."""
    d = _make_emul_dut()
    d.Open()
    result = d.read(adr=0x100, nWords=1)
    assert result == 0x0000
    # And caller-supplied emulation_return is honored:
    assert d.read(adr=0x100, nWords=1, emulation_return=0xDEAD) == 0xDEAD


def test_dut_write_in_emulation_does_not_raise():
    d = _make_emul_dut()
    d.Open()
    d.write(adr=0x100, val=0x1234)


def test_inherits_from_Dut_base():
    from openflow.dut.base import Dut
    d = _make_emul_dut()
    assert isinstance(d, Dut)
