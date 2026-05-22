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


def _try_call(obj: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    """Call ``obj.method_name(*args, **kwargs)`` if the method exists.

    Returns the method's result, or ``None`` if the method is missing
    (``AttributeError``) or raises ``NotImplementedError`` (the V1b stub
    pattern). Logs a warning in both cases so the engineer sees what's
    skipped during a bench run with partial driver coverage.

    This lets `setup_dmm` / `get_dmm` / `get_aux` work cleanly against the
    full set of real bench DMMs / DUT, against partial V1b stubs (`Dut`
    base raises NotImplementedError), and against V1a placeholder DMM/PSU
    stubs (which have no method at all yet). Each missing method is a clear
    log line, not a test failure.
    """
    method = getattr(obj, method_name, None)
    if method is None:
        logger.warning("%s.%s() not available — skipped",
                       type(obj).__name__, method_name)
        return None
    try:
        return method(*args, **kwargs)
    except NotImplementedError as e:
        logger.warning("%s.%s() not implemented (V1b stub): %s — skipped",
                       type(obj).__name__, method_name, e)
        return None


def setup_dmm(dmms: dict[str, Any]) -> None:
    """Configure each DMM for DC-current measurement at its expected range.

    ``dmms`` maps DMM keys (``dmm_c``, ``dmm_idd1v4``, …) to DMM driver
    instances. Entries that are ``None`` or absent are skipped, matching
    the ``if self.dmm_x != None`` guards in the source. DMM drivers that
    don't yet implement ``set_mode`` / ``set_range_current`` are skipped
    with a warning (lets V1b proceed against the placeholder DMM stub).
    """
    for key, range_A in _DMM_RANGES_A.items():
        dmm = dmms.get(key)
        if dmm is None:
            continue
        _try_call(dmm, "set_mode", isVoltage=False, isDc=True)
        _try_call(dmm, "set_range_current", range_A)


def get_dmm(dmms: dict[str, Any]) -> dict[str, float]:
    """Read each present DMM and return the readings keyed by ``out_*_A``.

    Preserves the source's ordering and last-write-wins ``out_ibat_A``
    behavior: when both ``dmm_c`` and ``dmm_ibat`` are provided, the
    ``dmm_ibat`` reading lands in ``out_ibat_A``. DMMs without a working
    ``get_measurement`` method contribute ``nan`` rather than crashing.
    """
    import math

    def _read(key: str) -> float:
        dmm = dmms.get(key)
        if dmm is None:
            return math.nan
        result = _try_call(dmm, "get_measurement")
        return float(result) if result is not None else math.nan

    out: dict[str, float] = {}
    # Order mirrors the original method body exactly.
    if dmms.get("dmm_c") is not None:
        out["out_ibat_A"] = _read("dmm_c")
    if dmms.get("dmm_idd1v4") is not None:
        out["out_idd1v4_A"] = _read("dmm_idd1v4")
    if dmms.get("dmm_idd1v8") is not None:
        out["out_idd1v8_A"] = _read("dmm_idd1v8")
    if dmms.get("dmm_idd2v5") is not None:
        out["out_idd2v5_A"] = _read("dmm_idd2v5")
    if dmms.get("dmm_iapt") is not None:
        out["out_iapt_A"] = _read("dmm_iapt")
    if dmms.get("dmm_ibat") is not None:
        # Last-write-wins for out_ibat_A — see module docstring.
        out["out_ibat_A"] = _read("dmm_ibat")
    if dmms.get("dmm_ifem1v2") is not None:
        out["out_ifem1v2_A"] = _read("dmm_ifem1v2")
    if dmms.get("dmm_ifem1v8") is not None:
        out["out_ifem1v8_A"] = _read("dmm_ifem1v8")
    return out


def get_aux(dut: Any) -> dict[str, float]:
    """Read the six auxadc/tempsens values from the DUT.

    Returns a dict keyed by the same ``out_*`` names the original
    ``Get_Aux`` method assigned on ``self``. DUT methods that aren't yet
    ported (V1b Dut stubs raise NotImplementedError) contribute ``nan``.
    """
    import math

    def _read(method: str) -> float:
        result = _try_call(dut, method)
        return float(result) if result is not None else math.nan

    return {
        "out_tempsens0_C":      _read("get_auxadc_tempsens0"),
        "out_tempsens1_C":      _read("get_auxadc_tempsens1"),
        "out_tempsens_int_raw": _read("get_auxadc_tempsens_int_raw"),
        "out_tempsens_int_C":   _read("get_auxadc_tempsens_int"),
        "out_auxadc_vbat":      _read("get_auxadc_vbat"),
        "out_tempsens_fem_C":   _read("get_fem_tempsens"),
    }
