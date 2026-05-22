"""Tests for ``openflow.rfengine.evt_base``.

These helpers were ported from ``U300_RFEngine_EVT_Base.py`` — three methods
(``Setup_DMM``, ``Get_DMM``, ``Get_Aux``) hoisted out of an OpenTAP TestStep
base class into module-level functions. The DMMs and DUT are passed in as
arguments instead of being instance attributes.

The original ``Setup_DMM`` / ``Get_DMM`` operated over a fixed set of eight
optional DMM handles (``dmm_c`` plus seven IDD/Ifem/Iapt/Ibat current meters).
The ported functions accept a single ``dmms`` mapping so callers can pass
whichever subset of meters their bench actually has.
"""
from __future__ import annotations

from typing import Any

import pytest

from openflow.rfengine.evt_base import get_aux, get_dmm, setup_dmm

# ---------------------------------------------------------------------------
# Fakes


class _FakeDMM:
    """Records ``set_mode`` / ``set_range_current`` / ``get_measurement`` calls."""

    def __init__(self, reading: float = 0.0) -> None:
        self.mode_calls: list[tuple[bool, bool]] = []
        self.range_calls: list[float] = []
        self.get_calls = 0
        self.reading = reading

    def set_mode(self, isVoltage: bool, isDc: bool) -> None:  # matches legacy API
        self.mode_calls.append((isVoltage, isDc))

    def set_range_current(self, value: float) -> None:
        self.range_calls.append(value)

    def get_measurement(self) -> float:
        self.get_calls += 1
        return self.reading


class _FakeDUT:
    """Stubs the six auxadc accessors used by ``Get_Aux``."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_auxadc_tempsens0(self) -> float:
        self.calls.append("tempsens0")
        return 25.5

    def get_auxadc_tempsens1(self) -> float:
        self.calls.append("tempsens1")
        return 26.0

    def get_auxadc_tempsens_int_raw(self) -> int:
        self.calls.append("tempsens_int_raw")
        return 1234

    def get_auxadc_tempsens_int(self) -> float:
        self.calls.append("tempsens_int")
        return 27.0

    def get_auxadc_vbat(self) -> float:
        self.calls.append("vbat")
        return 3.7

    def get_fem_tempsens(self) -> float:
        self.calls.append("fem_tempsens")
        return 28.0


# ---------------------------------------------------------------------------
# setup_dmm


def test_setup_dmm_configures_dmm_c_for_dc_current_with_10A_range() -> None:
    dmm_c = _FakeDMM()
    setup_dmm({"dmm_c": dmm_c})
    assert dmm_c.mode_calls == [(False, True)]
    assert dmm_c.range_calls == [10.0]


def test_setup_dmm_uses_1A_range_for_idd_meters() -> None:
    dmm_idd1v4 = _FakeDMM()
    dmm_idd1v8 = _FakeDMM()
    dmm_idd2v5 = _FakeDMM()
    setup_dmm(
        {
            "dmm_idd1v4": dmm_idd1v4,
            "dmm_idd1v8": dmm_idd1v8,
            "dmm_idd2v5": dmm_idd2v5,
        }
    )
    for dmm in (dmm_idd1v4, dmm_idd1v8, dmm_idd2v5):
        assert dmm.mode_calls == [(False, True)]
        assert dmm.range_calls == [1.0]


def test_setup_dmm_uses_10A_range_for_iapt_and_ibat() -> None:
    dmm_iapt = _FakeDMM()
    dmm_ibat = _FakeDMM()
    setup_dmm({"dmm_iapt": dmm_iapt, "dmm_ibat": dmm_ibat})
    for dmm in (dmm_iapt, dmm_ibat):
        assert dmm.mode_calls == [(False, True)]
        assert dmm.range_calls == [10.0]


def test_setup_dmm_uses_100mA_range_for_ifem_meters() -> None:
    dmm_ifem1v2 = _FakeDMM()
    dmm_ifem1v8 = _FakeDMM()
    setup_dmm({"dmm_ifem1v2": dmm_ifem1v2, "dmm_ifem1v8": dmm_ifem1v8})
    for dmm in (dmm_ifem1v2, dmm_ifem1v8):
        assert dmm.mode_calls == [(False, True)]
        assert dmm.range_calls == pytest.approx([0.1])


def test_setup_dmm_skips_none_entries() -> None:
    # Mix of present and None DMMs — only the present one should see calls.
    dmm_c = _FakeDMM()
    setup_dmm({"dmm_c": dmm_c, "dmm_idd1v4": None, "dmm_ibat": None})
    assert dmm_c.mode_calls == [(False, True)]


def test_setup_dmm_accepts_empty_mapping() -> None:
    # No DMMs at all — function should be a no-op.
    setup_dmm({})


# ---------------------------------------------------------------------------
# get_dmm


def test_get_dmm_reads_dmm_c_into_out_ibat_A() -> None:
    dmm_c = _FakeDMM(reading=0.5)
    result = get_dmm({"dmm_c": dmm_c})
    assert dmm_c.get_calls == 1
    assert result["out_ibat_A"] == 0.5


def test_get_dmm_reads_all_idd_meters_into_named_outputs() -> None:
    dmms = {
        "dmm_idd1v4": _FakeDMM(reading=0.12),
        "dmm_idd1v8": _FakeDMM(reading=0.18),
        "dmm_idd2v5": _FakeDMM(reading=0.25),
    }
    result = get_dmm(dmms)
    assert result["out_idd1v4_A"] == 0.12
    assert result["out_idd1v8_A"] == 0.18
    assert result["out_idd2v5_A"] == 0.25


def test_get_dmm_reads_iapt_ibat_ifem_meters() -> None:
    dmms = {
        "dmm_iapt": _FakeDMM(reading=1.0),
        "dmm_ibat": _FakeDMM(reading=2.0),
        "dmm_ifem1v2": _FakeDMM(reading=0.05),
        "dmm_ifem1v8": _FakeDMM(reading=0.07),
    }
    result = get_dmm(dmms)
    assert result["out_iapt_A"] == 1.0
    # When both ``dmm_c`` and ``dmm_ibat`` are present, the source assigns
    # ``out_ibat_A`` twice — second write wins. With no ``dmm_c`` the second
    # write is the only write, so the ``dmm_ibat`` reading lands in the output.
    assert result["out_ibat_A"] == 2.0
    assert result["out_ifem1v2_A"] == 0.05
    assert result["out_ifem1v8_A"] == 0.07


def test_get_dmm_ibat_overrides_dmm_c_when_both_present() -> None:
    # Source assigns out_ibat_A from dmm_c first, then dmm_ibat. The dmm_ibat
    # reading should land in the dict because it is written last.
    dmm_c = _FakeDMM(reading=99.9)
    dmm_ibat = _FakeDMM(reading=1.5)
    result = get_dmm({"dmm_c": dmm_c, "dmm_ibat": dmm_ibat})
    assert result["out_ibat_A"] == 1.5


def test_get_dmm_omits_outputs_for_absent_dmms() -> None:
    # Only dmm_c provided — only out_ibat_A should appear (no idd/iapt keys).
    result = get_dmm({"dmm_c": _FakeDMM(reading=0.5)})
    assert "out_idd1v4_A" not in result
    assert "out_iapt_A" not in result
    assert "out_ifem1v2_A" not in result


def test_get_dmm_empty_mapping_returns_empty_dict() -> None:
    assert get_dmm({}) == {}


# ---------------------------------------------------------------------------
# get_aux


def test_get_aux_reads_all_six_auxadc_values() -> None:
    dut = _FakeDUT()
    result = get_aux(dut)
    assert result == {
        "out_tempsens0_C": 25.5,
        "out_tempsens1_C": 26.0,
        "out_tempsens_int_raw": 1234,
        "out_tempsens_int_C": 27.0,
        "out_auxadc_vbat": 3.7,
        "out_tempsens_fem_C": 28.0,
    }


def test_get_aux_calls_each_dut_accessor_exactly_once() -> None:
    dut = _FakeDUT()
    get_aux(dut)
    assert sorted(dut.calls) == sorted(
        [
            "tempsens0",
            "tempsens1",
            "tempsens_int_raw",
            "tempsens_int",
            "vbat",
            "fem_tempsens",
        ]
    )


def test_get_aux_returns_dict_type() -> None:
    result: dict[str, Any] = get_aux(_FakeDUT())
    assert isinstance(result, dict)
