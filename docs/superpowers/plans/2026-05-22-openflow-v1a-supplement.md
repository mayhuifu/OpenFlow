# OpenFlow V1a Plan — Supplement (2026-05-22)

After review of the real UMT codebase (`UMT_Instruments 5/` with four production
OpenTAP packages: `UMT_Base`, `UMT_Instruments` ×80 drivers, `UMT_DUTs` ×~20
DUTs, `U300_RFEngine` ×13 EVT tests), V1a's scope expands.

**Main plan file:** `2026-05-22-openflow-v1a.md` (the 30-task plan, still
authoritative for Tasks 1–6, 10–14, 15–30).
**This file:** delta for Tasks 7–9 and Phase 2 transformer additions.

## What's changing

Phase 1 grows from 14 tasks to 17 (adds 3). Phase 2 grows from 12 tasks to 13
(adds 1 transformer). Phase 3 unchanged. New total: **34 tasks** (was 30).

| # | Old plan | New plan |
|---|---|---|
| 7 | CMW100 raw-PyVISA driver (TDD) | **Task 7: CMW100AMixin port — TX-EVM subset** |
| — | — | **Task 7a (NEW): CMW100GMixin port** |
| — | — | **Task 7b (NEW): CMW100 façade class** |
| 8 | MockCMW100 (separate fake class) | **Task 8: Instrument stub modules** (mock CMW100 = `CMW100(is_emulation=True)`) |
| 9 | StubDUT with `__getattr__` raise | **Task 9: `Dut` base — port of UMT_DUT** |
| — | — | **Task 9a (NEW): rfengine modules** — Deembedding, Testconditions_Limits, Calibration_File |
| 10–14 | unchanged conceptually | Fixture list now includes `wfg, dmm_c, dmm_v, sg, sa, psu, osc`; integration test runs against real CMW100 emulation mode |
| 15–26 | 10 libcst transformers | **+ Task 25a (NEW): `RewriteImportPaths` transformer** (`UMT_Instruments.X` → `openflow.instruments.x`; `U300_RFEngine.X` → `openflow.rfengine.x`) |
| 27–30 | unchanged | unchanged |

## New / revised task content

### Task 7 (revised): CMW100AMixin port — TX-EVM subset

**Files:**
- Create: `openflow/instruments/cmw100_a.py`
- Create: `tests-internal/test_cmw100_a_mixin.py`
- Modify: `pyproject.toml` (add R&S SDK deps)

**Scope:** port only the methods the TX EVM Power Sweep test invokes — `__init__`, `Open(visa_address)`, `Close()`, `setup_NrTx(...)`, `meas_NrTxAll()`, `meas_NrTxEVM(use_cached)`, `meas_NrTxPower(use_cached, n_retry)`. Source lines in original `CMW100A.py`:
- `__init__` → lines 67–73 (~7 lines)
- `Open` / `Close` → lines 75–102 (~28 lines)
- `setup_NrTx` → lines 694–1023 (~330 lines)
- `meas_NrTxAll` → lines 1047–1077 (~30 lines)
- `meas_NrTxEVM` → lines 1078–1124 (~47 lines)
- `meas_NrTxPower` → lines 1337–1385 (~49 lines)

Total: ~490 lines of code, after stripping the OpenTAP imports (lines 24–48 of CMW100A.py).

**Transformations to apply (line-by-line):**
1. Drop `from opentap import *`, `from System import …`, `import OpenTap`, `from System.ComponentModel import …`, `from System.Collections.Generic import …`.
2. Keep `from RsCmwBase import *`, `from RsCmwGprfMeas import *`, `from RsCmwNrFr1Meas import *` (and their `.enums` / `.repcap` siblings actually referenced).
3. Drop `from .CM import CM`, `from .SA import SA` (we use mixins directly, not OpenTAP-inheriting wrapper class).
4. Replace `self.log = Trace(self)` → `self.log = logging.getLogger(__name__)` at top of `__init__`. Add `import logging` at module top.
5. Replace any `self.log.Info(...)` → `self.log.info(...)`; `Warning` → `warning`; `Error` → `error`; `Debug` → `debug`.
6. **Do not** port the `class CMW100A(SA):` wrapper class at the bottom of CMW100A.py — that's the OpenTAP-bound facade, replaced by our own façade in Task 7b.

**Add to `pyproject.toml` `dependencies` list:**
```toml
"RsCmwBase>=4.0",
"RsCmwGprfGen>=4.0",
"RsCmwGprfMeas>=4.0",
"RsCmwLteSig>=4.0",
"RsCmwLteMeas>=4.0",
"RsCmwNrFr1Meas>=4.0",
```
(Remove the `pyvisa>=1.14` and `pyvisa-py>=0.7` lines we added in Task 1 — no longer needed.)

**Tests** (TDD):
- `test_emulation_mode_init_does_not_open_session` — `CMW100AMixin(); m.is_emulation = True; m.Open(visa_address=None)` does not raise.
- `test_setup_NrTx_emulation_returns_None` — `m.setup_NrTx(in_band="n78", in_freq_pll_Hz=3.6e9, ...)` returns None without touching R&S SDK.
- `test_meas_NrTxEVM_emulation_returns_plausible_float` — returns a float in [2.0, 3.0) (matches the existing `2.0 + np.random.rand()` pattern).
- `test_meas_NrTxPower_emulation_returns_plausible_float` — returns a float in [23.0, 24.0).
- `test_meas_NrTxAll_emulation_returns_None`.

Real-hardware path tests deferred to V1b (require bench).

**Commit:** `feat(instruments): CMW100AMixin — port of TX EVM measurement methods from UMT_Instruments/CMW100A.py`

---

### Task 7a (NEW): CMW100GMixin port

**Files:**
- Create: `openflow/instruments/cmw100_g.py`
- Create: `tests-internal/test_cmw100_g_mixin.py`

**Scope:** port `__init__`, `Open(VisaAddress)`, `Close()`, `set_arb_signal_rf(...)`, `set_rf_power(power_in_dBm)`, plus the connector-mapping helper inside `set_arb_signal_rf`. Source lines in original `CMW100G.py`:
- `__init__` → 61–65
- `Open` / `Close` → 67–83
- `set_arb_signal_rf` → 106–174 (the full method — keep the 5G + LTE + CW waveform-file branches)
- `set_rf_power` → 319–325

Skip: `set_arb_signal_rf_stop`, `set_two_tone_signal_rf`, `set_two_tone_signal_rf_stop`, `add_blocker_CW` (V2 work).

**Transformations:** same as Task 7 — strip OpenTAP imports, replace `Trace` with `logging`, etc.

**Tests** (TDD):
- `test_emulation_mode_set_arb_signal_rf_returns_None_silently`
- `test_emulation_mode_set_rf_power_returns_None_silently`
- `test_signal_type_unsupported_sets_error_attribute` — `m = CMW100GMixin(); m.is_emulation = False;` calling `set_arb_signal_rf(signal_type="X")` sets `m.error` to a string containing "X is not supported".

**Commit:** `feat(instruments): CMW100GMixin — port of generator methods from UMT_Instruments/CMW100G.py`

---

### Task 7b (NEW): CMW100 façade class

**Files:**
- Create: `openflow/instruments/cmw100.py`
- Create: `tests-internal/test_cmw100_facade.py`

**Scope:** the public class tests interact with. Holds an instance of `CMW100AMixin` (as `self.cmwa`) and `CMW100GMixin` (as `self.cmwg`). Public methods delegate. Mirrors the original `CMW100.py` minus OpenTAP.

```python
"""R&S CMW100 façade — combines the analyzer (mixin A) and generator (mixin G)."""
from __future__ import annotations

import logging
from openflow.instruments.base import Instrument
from openflow.instruments.cmw100_a import CMW100AMixin
from openflow.instruments.cmw100_g import CMW100GMixin


class CMW100(Instrument):
    def __init__(self, visa_address: str = "", *, is_emulation: bool = False) -> None:
        super().__init__(visa_address)
        self.log = logging.getLogger(__name__)
        self.is_emulation = is_emulation
        self.cmwa = CMW100AMixin()
        self.cmwa.is_emulation = is_emulation
        self.cmwg = CMW100GMixin()
        self.cmwg.is_emulation = is_emulation

    def open(self) -> None:
        self.cmwa.Open(self.resource)
        self.cmwg.Open(self.resource)

    def close(self) -> None:
        self.cmwa.Close()
        self.cmwg.Close()

    def write(self, scpi: str) -> None:
        raise NotImplementedError("CMW100 uses R&S SDK; raw SCPI not supported.")

    def query(self, scpi: str) -> str:
        raise NotImplementedError("CMW100 uses R&S SDK; raw SCPI not supported.")

    # --- NR Tx measurement surface (delegates to mixin A) ---
    def setup_NrTx(self, **kwargs: object) -> None:
        return self.cmwa.setup_NrTx(**kwargs)

    def meas_NrTxAll(self) -> None:
        return self.cmwa.meas_NrTxAll()

    def meas_NrTxEVM(self, *, use_cached: bool = False) -> float:
        return self.cmwa.meas_NrTxEVM(use_cached=use_cached)

    def meas_NrTxPower(self, *, use_cached: bool = False) -> float:
        return self.cmwa.meas_NrTxPower(use_cached=use_cached)

    # --- Generator surface (delegates to mixin G) ---
    def set_arb_signal_rf(self, **kwargs: object) -> None:
        return self.cmwg.set_arb_signal_rf(**kwargs)

    def set_rf_power(self, power_in_dBm: float) -> None:
        return self.cmwg.set_rf_power(power_in_dBm=power_in_dBm)
```

**Tests** (TDD):
- `test_construction_with_is_emulation_True_propagates_to_mixins`
- `test_open_then_close_in_emulation_does_not_raise`
- `test_meas_NrTxEVM_round_trip_in_emulation`
- `test_setup_NrTx_then_meas_NrTxAll_in_emulation`
- `test_write_query_raises_NotImplementedError` (we use R&S SDK, not raw SCPI)

**Commit:** `feat(instruments): CMW100 façade combining cmwa/cmwg mixins, is_emulation pass-through`

---

### Task 8 (revised): Instrument stub modules

**Files:**
- Create: `openflow/instruments/stubs.py`
- Create: `tests-internal/test_instrument_stubs.py`

**Scope:** empty placeholder classes so the migrated TX EVM test's imports resolve at collection time. The TX EVM test references types: `WFG`, `DMM`, `PSU`, `OSC`, `SG`, `SA`. None of them are actually used by V1a (the test is `--collect-only` for those instruments — no execution).

```python
"""V1a placeholder classes for instruments the migrated tests import but do not exercise.
Each port lands in V2 when the corresponding test moves over."""
from __future__ import annotations

from openflow.instruments.base import Instrument


class _UnimplementedInstrument(Instrument):
    """Common parent — raises NotImplementedError on any method call beyond Instrument ABC."""
    def open(self) -> None:
        raise NotImplementedError(f"{type(self).__name__}: real port lands in V2")
    def close(self) -> None: pass
    def write(self, scpi: str) -> None:
        raise NotImplementedError(f"{type(self).__name__}: real port lands in V2")
    def query(self, scpi: str) -> str:
        raise NotImplementedError(f"{type(self).__name__}: real port lands in V2")


class WFG(_UnimplementedInstrument): ...
class DMM(_UnimplementedInstrument): ...
class PSU(_UnimplementedInstrument): ...
class OSC(_UnimplementedInstrument): ...
class SG(_UnimplementedInstrument): ...
class SA(_UnimplementedInstrument): ...
```

**Tests:**
- `test_each_stub_is_subclass_of_Instrument`
- `test_each_stub_instantiates_with_resource_arg`
- `test_open_raises_NotImplementedError_with_class_name_and_V2`

**Commit:** `feat(instruments): WFG/DMM/PSU/OSC/SG/SA stub classes — real ports defer to V2`

---

### Task 9 (revised): `Dut` base class — port of UMT_DUT

**Files:**
- Create: `openflow/dut/base.py`
- Create: `tests-internal/test_dut_base.py`

**Scope:** port `UMT_DUT.py` (only ~30 lines) into a plain Python base class.

```python
"""DUT base class — port of UMT_DUTs.UMT_DUT minus OpenTAP scaffolding."""
from __future__ import annotations

import logging
from typing import Any


class Dut:
    """Base for all DUT subclasses. Concrete DUTs (e.g. DUT_U300) override methods.
    V1a ships this base only; real U300 subclass lands in V1b."""

    def __init__(self) -> None:
        self.log = logging.getLogger(__name__)
        self.emulation = False
        self.name = type(self).__name__

    def open(self) -> None:
        self.log.info("%s open() — no-op base class", self.name)

    def close(self) -> None:
        self.log.info("%s close() — no-op base class", self.name)

    def get_id(self) -> str:
        self.log.warning("Dut.get_id() not implemented by subclass; returning placeholder")
        return "No_ID"

    def __getattr__(self, name: str) -> Any:
        # Allow the migrated test to *collect* even though it calls methods like
        # set_rfTxPower that only the V1b concrete DUT will implement.
        def _unimplemented(*args: object, **kwargs: object) -> None:
            raise NotImplementedError(
                f"Dut.{name}() — V1a base class. Concrete DUT (e.g. DUT_U300) lands in V1b.")
        return _unimplemented
```

Note: we keep both an explicit `get_id` (to mirror UMT_DUT exactly) AND the `__getattr__` fallback (to let the migrated TX EVM test collect; the test references methods like `set_rfTxPower`, `set_arb_signal_bb`, `set_rfAssignDlCarriers` that DUT_U300 will implement in V1b).

**Tests:**
- `test_Dut_can_be_instantiated`
- `test_get_id_returns_placeholder_string`
- `test_unknown_method_raises_NotImplementedError_mentioning_V1b`
- `test_open_close_log_at_info_level`

**Commit:** `feat(dut): Dut base class — port of UMT_DUTs.UMT_DUT, __getattr__ stubs for V1b subclasses`

---

### Task 9a (NEW): rfengine modules — Deembedding, Testconditions_Limits, Calibration_File

**Files:**
- Create: `openflow/rfengine/__init__.py`
- Create: `openflow/rfengine/deembedding.py` (port of `U300_RFEngine/Deembedding.py`, ~226 lines)
- Create: `openflow/rfengine/testconditions_limits.py` (port of `U300_RFEngine/Testconditions_Limits.py`, ~89 lines)
- Create: `openflow/rfengine/calibration_file.py` (port of `U300_RFEngine/Calibration_File.py`, ~761 lines)
- Create: `tests-internal/test_rfengine_deembedding.py`
- Create: `tests-internal/test_rfengine_testconditions_limits.py`
- Create: `tests-internal/test_rfengine_calibration_file.py`

**Scope:** mechanical port of three lookup-data loaders. These are mostly YAML/CSV parsing + dict access. No OpenTAP API calls in their core logic — just imports and the `Trace` logger to strip.

**Transformations (per file):**
1. Drop `from opentap import *`, `from System import …`, `import OpenTap`.
2. Drop `@attribute(...)` decorators at module level.
3. If the file defines a class with `property(<Type>, <default>)` declarations, those are V1a config inputs — leave them as plain Python class attributes (for now; later they move to YAML).
4. Replace `Trace` logger with `logging.getLogger`.
5. Keep `numpy`, `pandas`, `yaml`, `re` imports — those are real dependencies.

**Tests** (TDD per file, smoke-level — just construct + one lookup):
- `Testconditions_Limits.get(...)` → returns expected scalar from a small fixture YAML.
- `Deembedding.get(top="TX", ...)` → returns expected tuple.
- `Calibration_File.get_iq_dc_offset(...)` → returns 2-tuple of floats from a small fixture CSV.

Bonus dep additions to `pyproject.toml`:
```toml
"numpy>=1.26",
"pandas>=2.0",
```
(`pyyaml` already added in Task 1.)

**Commit:** `feat(rfengine): port Deembedding, Testconditions_Limits, Calibration_File from U300_RFEngine`

---

### Task 11 (revised): fixtures — add WFG, DMM, PSU, OSC, SG, SA, and rfengine fixtures

Modify Task 11's existing fixture set to add fixtures for the stub instruments and the rfengine loaders. The fixture functions are 4–6 lines each (load from config; instantiate; yield). Use the same `is_emulation` toggle.

Example additions:

```python
@pytest.fixture(scope="session")
def wfg(config: OpenFlowConfig) -> WFG:
    return WFG(config.instruments.get("wfg", InstrumentConfig(resource="")).resource)

@pytest.fixture(scope="session")
def deembedding(config: OpenFlowConfig) -> Deembedding:
    return Deembedding(config_path=config.deembedding_path)
```

Add `dmm_c`, `dmm_v` as named DMM instances (the TX EVM test uses two — one for current, one for voltage).

---

### Task 12 (revised): integration test now uses real CMW100 emulation

Replace the synthetic `MockCMW100` in Task 12 with the actual `CMW100(visa_address="MOCK", is_emulation=True)`. The test exercises the real `setup_NrTx`, `meas_NrTxAll`, `meas_NrTxEVM`, `meas_NrTxPower` code paths under emulation mode — proving the port works end-to-end.

```python
@pytest.mark.testcase("U300B0-MOCK-INT-001")
@pytest.mark.parametrize("target_power", [-10.0, 0.0, 10.0])
def test_emulation_tx_evm_round_trip(cmw100, config, results, target_power):
    cmw100.setup_NrTx(in_band=config.band, in_freq_pll_Hz=config.ul_freq_pll_Hz,
                      in_rfbw_Hz=config.rfbw_Hz, in_tx_power_dBm=target_power,
                      in_modulation=config.modulation, in_ul_config=config.ul_config,
                      in_scs_Hz=config.scs_Hz)
    cmw100.meas_NrTxAll()
    p = cmw100.meas_NrTxPower(use_cached=True)
    e = cmw100.meas_NrTxEVM(use_cached=True)
    results.publish(target_dBm=target_power, reported_dBm=p, reported_evm_pct=e)
    # Emulation returns 23+rand for power, 2+rand for EVM — sanity bounds:
    assert 22.5 < p < 24.5
    assert 1.5 < e < 3.5
```

---

### Task 25a (NEW): `RewriteImportPaths` libcst transformer

**Files:**
- Modify: `openflow/migrate/transformers.py` (add new transformer class)
- Create: `tests-internal/test_migrate_rewrite_import_paths.py`
- Modify: `openflow/migrate/pipeline.py` (add to chain after StripOpenTapImports)

**Scope:** rewrite `from UMT_Instruments.X import Y` → `from openflow.instruments.x import Y` (lower-case the module name). Same for `UMT_DUTs.UMT_DUT` → `openflow.dut.base.Dut`, `U300_RFEngine.Deembedding` → `openflow.rfengine.deembedding`, etc.

Mapping (hard-coded in V1a; could be config-driven later):
```python
_IMPORT_REWRITES = {
    "UMT_Instruments.CMW100":          ("openflow.instruments.cmw100",          "CMW100"),
    "UMT_Instruments.WFG":             ("openflow.instruments.stubs",           "WFG"),
    "UMT_Instruments.DMM":             ("openflow.instruments.stubs",           "DMM"),
    "UMT_Instruments.PSU":             ("openflow.instruments.stubs",           "PSU"),
    "UMT_Instruments.OSC":             ("openflow.instruments.stubs",           "OSC"),
    "UMT_Instruments.SG":              ("openflow.instruments.stubs",           "SG"),
    "UMT_Instruments.SA":              ("openflow.instruments.stubs",           "SA"),
    "UMT_DUTs.UMT_DUT":                ("openflow.dut.base",                    "Dut"),
    "U300_RFEngine.Deembedding":       ("openflow.rfengine.deembedding",        "Deembedding"),
    "U300_RFEngine.Testconditions_Limits": ("openflow.rfengine.testconditions_limits", "Testconditions_Limits"),
    "U300_RFEngine.Calibration_File":  ("openflow.rfengine.calibration_file",   "Calibration_File"),
    # U300_RFEngine_EVT_Base does NOT have an openflow equivalent — the migrator drops it
    # since the test no longer inherits from anything.
}
_IMPORTS_TO_DROP = {"U300_RFEngine.U300_RFEngine_EVT_Base", "UMT_Base.UMT_TestCase"}
```

Importing `UMT_DUT` → `Dut` is a rename (`from openflow.dut.base import Dut as UMT_DUT` to preserve test-code references, OR a separate `RenameSymbols` pass — pick whichever is simpler).

**Tests:**
- `test_rewrites_UMT_Instruments_CMW100_import`
- `test_rewrites_U300_RFEngine_Deembedding_import`
- `test_drops_U300_RFEngine_EVT_Base_import`
- `test_drops_UMT_Base_UMT_TestCase_import`
- `test_leaves_numpy_re_time_imports_intact`

**Pipeline insertion point:** after `StripOpenTapImports`, before the body-rewrite transformers.

**Commit:** `feat(migrate): RewriteImportPaths transformer for UMT → openflow path translation`

---

## Updated Definition of Done for V1a

(Replaces the DoD block at the end of the main plan.)

- [ ] `uv sync` succeeds on a fresh clone.
- [ ] `uv run ruff check` exits 0.
- [ ] `uv run mypy openflow` exits 0.
- [ ] `uv run pytest tests-internal` — all tests green (~35–40 tests total including new module tests).
- [ ] `uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py --openflow-config=tests/configs/u300b0_evt.yaml --collect-only` collects without error.
- [ ] `uv run pytest tests-internal/test_plugin_integration.py` runs the **real CMW100 in `is_emulation=True` mode** through `setup_NrTx → meas_NrTxAll → meas_NrTxEVM → meas_NrTxPower` end-to-end and emits the expected `report.json` shape.
- [ ] `uv run openflow migrate <some OpenTAP test>.py` produces a syntactically valid test file with rewritten import paths.
- [ ] CI green on both `ubuntu-latest` and `windows-latest`.
- [ ] Spec Open Question #1 is resolved (it is — see spec Section 8); Open Questions #2–6 acknowledged by reviewer.

V1b — running the migrated demo end-to-end against real CMW100 hardware + real U300 DUT — remains a separate plan, contingent on porting `DUT_U300` and `DUT_FT2232H` from the UMT codebase.
