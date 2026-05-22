"""EVT bench helpers ported from ``U300_RFEngine_EVT_Base.py``.

In the OpenTAP source these three routines (``Setup_DMM``, ``Get_DMM``,
``Get_Aux``) lived as instance methods on a base TestStep class so that
subclasses could share DMM/DUT plumbing through inheritance. After the V1c
migration each TX/RX test is a plain pytest function — there is no class
left to inherit from, so the helpers are exposed here as module-level
functions that take their DMM and DUT handles as arguments.

Faithfulness notes:

* The original ``Setup_DMM`` / ``Get_DMM`` operated over a fixed set of
  eight optional DMM attributes (``dmm_c`` plus the IDD/Ifem/Iapt/Ibat
  current meters). We preserve the same eight keys but accept them as a
  ``dmms`` mapping, so callers can pass whichever subset their bench
  actually exposes. ``None`` entries are skipped, matching the original
  ``if self.dmm_x != None`` guards.
* ``Get_DMM`` / ``Get_Aux`` originally wrote their results into ``self.out_*``
  attributes. With no instance to write to, we return a dict keyed by the
  same ``out_*`` names — callers can either consume it directly or splat
  it into their own results container.
* The ``out_ibat_A`` double-assignment in the original ``Get_DMM`` (once
  from ``dmm_c``, once from ``dmm_ibat``) is preserved: when both meters
  are present the ``dmm_ibat`` reading wins, matching the source's
  last-write-wins semantics.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Mapping from DMM key -> current range (in A) to program during setup.
# Matches the per-DMM ranges hard-coded in the original ``Setup_DMM``.
_DMM_RANGES_A: dict[str, float] = {
    "dmm_c": 10.0,
    "dmm_idd1v4": 1.0,
    "dmm_idd1v8": 1.0,
    "dmm_idd2v5": 1.0,
    "dmm_iapt": 10.0,
    "dmm_ibat": 10.0,
    "dmm_ifem1v2": 0.1,
    "dmm_ifem1v8": 0.1,
}


def setup_dmm(dmms: dict[str, Any]) -> None:
    """Configure each DMM for DC-current measurement at its expected range.

    ``dmms`` maps DMM keys (``dmm_c``, ``dmm_idd1v4``, …) to DMM driver
    instances. Entries that are ``None`` or absent are skipped, matching
    the ``if self.dmm_x != None`` guards in the source.
    """
    for key, range_A in _DMM_RANGES_A.items():
        dmm = dmms.get(key)
        if dmm is None:
            continue
        dmm.set_mode(isVoltage=False, isDc=True)
        dmm.set_range_current(range_A)


def get_dmm(dmms: dict[str, Any]) -> dict[str, float]:
    """Read each present DMM and return the readings keyed by ``out_*_A``.

    Preserves the source's ordering and last-write-wins ``out_ibat_A``
    behavior: when both ``dmm_c`` and ``dmm_ibat`` are provided, the
    ``dmm_ibat`` reading lands in ``out_ibat_A``.
    """
    out: dict[str, float] = {}
    # Order mirrors the original method body exactly.
    if dmms.get("dmm_c") is not None:
        out["out_ibat_A"] = dmms["dmm_c"].get_measurement()
    if dmms.get("dmm_idd1v4") is not None:
        out["out_idd1v4_A"] = dmms["dmm_idd1v4"].get_measurement()
    if dmms.get("dmm_idd1v8") is not None:
        out["out_idd1v8_A"] = dmms["dmm_idd1v8"].get_measurement()
    if dmms.get("dmm_idd2v5") is not None:
        out["out_idd2v5_A"] = dmms["dmm_idd2v5"].get_measurement()
    if dmms.get("dmm_iapt") is not None:
        out["out_iapt_A"] = dmms["dmm_iapt"].get_measurement()
    if dmms.get("dmm_ibat") is not None:
        # Last-write-wins for out_ibat_A — see module docstring.
        out["out_ibat_A"] = dmms["dmm_ibat"].get_measurement()
    if dmms.get("dmm_ifem1v2") is not None:
        out["out_ifem1v2_A"] = dmms["dmm_ifem1v2"].get_measurement()
    if dmms.get("dmm_ifem1v8") is not None:
        out["out_ifem1v8_A"] = dmms["dmm_ifem1v8"].get_measurement()
    return out


def get_aux(dut: Any) -> dict[str, float]:
    """Read the six auxadc/tempsens values from the DUT.

    Returns a dict keyed by the same ``out_*`` names the original
    ``Get_Aux`` method assigned on ``self``.
    """
    tempsens0 = dut.get_auxadc_tempsens0()
    tempsens1 = dut.get_auxadc_tempsens1()
    tempsens_int_raw = dut.get_auxadc_tempsens_int_raw()
    tempsens_int = dut.get_auxadc_tempsens_int()
    meas_auxadc_vbat = dut.get_auxadc_vbat()
    tempsens_fem = dut.get_fem_tempsens()

    return {
        "out_tempsens0_C": tempsens0,
        "out_tempsens1_C": tempsens1,
        "out_tempsens_int_raw": tempsens_int_raw,
        "out_tempsens_int_C": tempsens_int,
        "out_auxadc_vbat": meas_auxadc_vbat,
        "out_tempsens_fem_C": tempsens_fem,
    }
