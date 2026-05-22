# OpenFlow — v1 Design & Product Roadmap (Python pivot)

**Status:** Draft for engineering review
**Date:** 2026-05-22
**Supersedes:** `2026-05-21-openflow-v1-design.md` (C#/OpenTAP runner — archived as tag `v0.1.0-csharp-archived` and branch `archive/csharp-runner`)
**Audience:** Engineering reviewer(s)

---

## 1. What is OpenFlow?

OpenFlow is a **bare-metal Python test framework** for RF / baseband hardware test
automation. It replaces the OpenTAP-based test harness currently in use. Tests
are normal Python files that look like pytest tests, with:

- One test case = one `def test_<name>(...)` (no class inheritance from a framework base, no `Run()` lifecycle method)
- Sweeps via `@pytest.mark.parametrize` (no manual nested loops with verdict bookkeeping)
- Verdicts via plain `assert` (no `UpgradeVerdict(OpenTap.Verdict.Fail)`)
- Instrument access via pytest fixtures (no `property(SA, None).add_attribute(OpenTap.Display(...))`)
- Configuration in YAML (band, bandwidth, gain tables, deembedding paths, limits) — not hard-coded in Python or buried in OpenTAP `.TapPlan` XML
- Results emitted by a `results.publish(...)` fixture call — one final JSON report per test session

### Why pivot away from OpenTAP

After engineering review of the C# v0.1.0 runner, the conclusion was that
**OpenTAP itself — not the runner around it — is the source of friction**. The
two reference test cases (`U300B0_RFEB_EVT_RX_Gain_Accuracy.py` and
`U300B0_RFEB_EVT_TX_EVM_Power_Sweep.py`) show the pattern: ~30 lines of OpenTAP
scaffolding (`from opentap import *`, `import clr`, `@attribute(OpenTap.Display(...))`,
`property(Double, ...).add_attribute(...)`, `UpgradeVerdict`, `PublishResult`,
`super().Run()`) wrap ~100 lines of actual RF logic. The scaffolding is where
HW engineers spend their debugging time — not on RF problems, but on test-framework
problems.

The new direction inverts the cost: the framework gets out of the way, the RF
engineer reads and writes plain Python.

### Comparison

OpenTAP-Python today (excerpt from the Rx Gain Accuracy test):

```python
@attribute(OpenTap.Display("U300B0_RFEB_EVT_RX_Gain_Accuracy", "...", "..."))
@attribute(OpenTap.AllowAnyChild())
class U300B0_RFEB_EVT_RX_Gain_Accuracy(U300_RFEngine_EVT_Base):
    in_rx_power_backoff_dB = property(Double, 10.0) \
        .add_attribute(OpenTap.Display("set_rx_power_backoff_dB", "...", "RF Parameters"))\
        .add_attribute(OpenTap.MetaData(True))
    vsa = property(SA, None).add_attribute(OpenTap.Display("VSA", "...", "Instruments"))
    sg  = property(SG, None).add_attribute(OpenTap.Display("SG", "...", "Instruments"))
    dut = property(UMT_DUT, None).add_attribute(OpenTap.Display("DUT", "...", "DUT"))

    def Run(self):
        super().Run()
        for gain in self.rx_gain_table:
            ...
            if abs(self.out_rx_gain_delta) <= target_gain_delta:
                self.UpgradeVerdict(OpenTap.Verdict.Pass)
            else:
                self.UpgradeVerdict(OpenTap.Verdict.Fail)
            self.PublishResult()
```

Bare-metal Python after the migration:

```python
TESTCASE_ID  = "U300B0-RFE-EVT-002"
RX_GAIN_TABLE = [61, 58, 55, 52, 49, 46, 43, 40, 37, 34, 30, 27, 24, 21, 18, 15, 12, 9, 6, 3, 0]

@pytest.mark.testcase(TESTCASE_ID)
@pytest.mark.parametrize("gain", RX_GAIN_TABLE)
def test_rx_gain_accuracy(dut, vsa, sg, config, results, gain):
    target = config.limit("GAIN_DELTA", band=config.band, bandwidth_hz=config.rfbw_hz)
    deemb  = config.deembedding(top="RX", uldl=config.dl_config_active, band=config.band, freq=config.dl_freq_pll_hz)

    dut.cmd_initialize()
    dut.set_rfAssignDlCarriers(...)
    predicted = dut.set_rfRxGain(gain)[config.rx_idx]

    rx_level_dbm = -predicted - config.rx_power_backoff_dB
    sg.set_arb_signal_rf(..., power_level=rx_level_dbm - deemb.rfeb - deemb.ant)
    dut.setup_NRRx(sa=vsa, ...)

    rx_gain_delta = (dut.meas_NrRxPower(sa=vsa, ...) - deemb.bb - dut.dbm_to_dbv(rx_level_dbm)) - predicted

    results.publish(gain_setting=gain, rx_gain_delta=rx_gain_delta, ...)
    assert abs(rx_gain_delta) <= target, f"Gain error {rx_gain_delta:.2f} dB exceeds {target} dB target"
```

---

## 2. v1 Scope

### Success criterion

From a clean checkout on a Windows or Linux lab machine with NI-VISA / Keysight IO Libraries already installed:

```sh
uv sync
uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py --config tests/configs/u300b0_evt.yaml --report report.json
```

…runs the Tx EVM Power Sweep test against a real CMW100, writes one JSON
report file, and exits 0 (all parametrized cases passed) or 1 (any failed).

Additionally:

```sh
uv run openflow migrate path/to/U300B0_RFEB_EVT_TX_EVM_Power_Sweep.py
```

…rewrites an OpenTAP-Python test source file into a bare-metal pytest test
file, preserving comments and most formatting, marking any pattern it can't
auto-convert with a `# TODO[openflow-migrate]:` comment.

### Explicit non-goals for v1

- Web dashboard for historical results (deferred to v5+)
- Bench reservation / multi-DUT orchestration (v3+)
- Result database (v4)
- Migration of every test in the U300 suite (v2 — once v1 proves the converter)
- Drivers for non-CMW100 instruments (SG / SA / WFG / DMM stubbed for v1; full impls in v3)
- DUT driver from scratch — v1 either imports the existing `UMT_DUT` (if plain Python) or shims it (see §8 open question)

### Target runtime

Python 3.11+, cross-platform (Windows for real benches, Ubuntu for fixture-based CI). Real instrument I/O on Windows requires NI-VISA or Keysight IO Libraries installed system-wide; the `pyvisa` Python package adapts on top of either.

---

## 3. Architecture

A single Python package `openflow`, plus a sibling `tests/` directory holding the actual RF tests. uv-managed `pyproject.toml`.

```
openflow/                        # the package
├── __init__.py
├── plugin.py                    # pytest plugin entry point + hooks + markers
├── fixtures.py                  # cmw100, dut, config, results fixtures
├── config.py                    # YAML loader + pydantic models
├── results.py                   # Result accumulator → JSON/HTML writer
├── instruments/
│   ├── __init__.py
│   ├── base.py                  # Instrument base (connect / close / SCPI helpers)
│   └── cmw100.py                # CMW100 driver (setup_NrTx, meas_NrTxEVM, …)
├── dut/
│   ├── __init__.py
│   └── stub.py                  # placeholder until UMT_DUT status is resolved
└── migrate/
    ├── __init__.py
    ├── cli.py                   # `openflow migrate` command
    ├── transformers.py          # libcst codemods (one class per pattern)
    └── patterns.md              # before/after migration cookbook

tests/                           # real RF tests using the framework
├── conftest.py                  # wires openflow plugin + project fixtures
├── configs/
│   └── u300b0_evt.yaml          # bands, limits, deembedding paths, modulations
└── test_u300b0_rfeb_evt_tx_evm_power_sweep.py   # the ported MVP test

tests-internal/                  # framework's own tests (NOT real RF tests)
├── test_config_loader.py
├── test_results_publisher.py
└── test_migrate_*.py            # one per libcst transformer

pyproject.toml                   # uv-managed; deps below
uv.lock
.github/workflows/ci.yml         # build + tests-internal + smoke on Win/Linux
README.md
LICENSE                          # MIT
```

**Runtime dependencies:** `pytest`, `pyvisa`, `pydantic`, `pyyaml`, `rich` (CLI formatting), `libcst` (migration only).
**Dev dependencies:** `pytest-cov`.

### Why a pytest plugin and not a custom runner

pytest gives us, free, every feature a custom runner would need to reinvent:
test discovery, parametrize, fixtures with lifecycle, ordering, filtering by
marker, reporting, exit-code conventions, parallelization (pytest-xdist if
needed later), live-log capture, junit-xml output, IDE integration, and a
massive plugin ecosystem. The framework just adds the *domain* on top: instrument
fixtures, YAML config, and a result publisher.

---

## 4. Data flow

### Test execution

```
pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py --config tests/configs/u300b0_evt.yaml --report report.json
   │
   ├─ openflow plugin loads
   │     reads --config → builds typed Config (pydantic)
   │     registers cmw100, dut, config, results fixtures
   │
   ├─ pytest collects test, applies @pytest.mark.parametrize(modulation × power)
   │
   ├─ For each parametrized case:
   │     fixtures spin up in order:
   │         config   (already loaded; session-scoped)
   │         cmw100   (PyVISA open; session-scoped)
   │         dut      (UMT_DUT or shim; session-scoped)
   │         results  (session-scoped accumulator)
   │     test body runs: DUT setup → CMW100 measure → results.publish(...) → assert
   │
   └─ session_finish hook
         results.write_json(report.json)
         (optional) results.write_html(report.html)

Exit code: 0 if all pass, 1 if any fail (pytest standard).
```

### Migration

```
uv run openflow migrate path/to/U300B0_RFEB_EVT_TX_EVM_Power_Sweep.py
   │
   ├─ libcst.parse_module
   ├─ Run transformer pipeline (in order):
   │     1. StripOpenTapImports          ─ rm `from opentap import *`, `import OpenTap`, `import clr`, `clr.AddReference(...)`
   │     2. StripAttributeDecorators     ─ rm `@attribute(OpenTap.Display(...))`, `@attribute(OpenTap.AllowAnyChild())`
   │     3. ExtractTestcaseId            ─ `Testcase_ID = property(String, "X-Y-Z")...` → module-level `TESTCASE_ID = "X-Y-Z"`
   │     4. ConvertInstrumentProperties  ─ `vsa = property(SA, None).add_attribute(...)` → fixture name in function signature
   │     5. ConvertInputProperties       ─ `in_rx_power_backoff_dB = property(Double, 10.0)…` → YAML config key
   │     6. ConvertClassToTestFunction   ─ `class X(U300_RFEngine_EVT_Base): … def Run(self): …` → `def test_x(fixtures): …`
   │     7. ConvertVerdictCalls          ─ `self.UpgradeVerdict(OpenTap.Verdict.Fail)` → `assert False, "…"`  (or accumulator pattern, see patterns.md)
   │     8. ConvertLogCalls              ─ `self.log.Info(...)` → `logger.info(...)`
   │     9. ConvertPublishResult         ─ `self.PublishResult()` + `self.out_*=…` → `results.publish(...)`
   │     10. StripLifecycleStubs         ─ rm `__init__`, `PreRun`, `PostRun` if they only call `super()`
   │
   ├─ Emit transformed module as test_<snake_case_name>.py next to original
   └─ Print summary: "Converted 87/92 nodes. 5 patterns require manual review:
                       line 240: complex verdict logic — see patterns.md#mpr-conditional-verdict"
```

**Each transformer is independently unit-testable** against a short before/after code snippet — this is the lowest-risk way to build the converter.

---

## 5. Error handling

| Condition                                      | Behavior                                                                     | Exit code |
| ---------------------------------------------- | ---------------------------------------------------------------------------- | --------- |
| Missing or invalid YAML config                 | pytest collection error with file/line                                       | 2         |
| `--config` path does not exist                 | Clear error in plugin's `pytest_addoption` hook                              | 2         |
| CMW100 connection refused / timeout            | Fixture raises `InstrumentConnectError`; dependent tests **errored, not failed**; other tests still run | 1 (if no others pass) |
| DUT communication timeout mid-test             | Test fails normally with traceback                                           | 1         |
| `assert` failure (verdict)                     | Standard pytest failure with rich assert message                             | 1         |
| Ctrl+C                                         | pytest's standard SIGINT handling — clean teardown of fixtures               | 130       |
| Migration tool: unrecognized pattern           | Preserve original code with `# TODO[openflow-migrate]: <reason>` comment + end-of-run summary | 0 (success with manual TODOs) |

**Errored ≠ Failed.** An instrument that can't connect is a setup problem, not
a test failure — the report must distinguish these so an engineer can tell
"my code is bad" from "the bench is broken."

---

## 6. Testing strategy

Two layers, **neither requires real hardware**:

1. **Unit tests** (`tests-internal/`): one test file per framework module.
   - `test_config_loader.py` — YAML parsing, pydantic validation, error messages
   - `test_results_publisher.py` — JSON shape, ordering, session-end hook
   - `test_migrate_<transformer>.py` — one file per libcst transformer, each asserts before/after string transformations on real snippets from the two reference OpenTAP files

2. **Mock-instrument integration test**: a `MockCMW100` (in-process fake responding to SCPI command strings) wired in via fixture override. Verifies the pytest plugin, fixture lifecycle, parametrize, and result publishing end-to-end without a real bench.

CI on GitHub Actions runs both layers on **`ubuntu-latest`** and **`windows-latest`**. Live-bench tests live in the engineer's local workflow, not CI.

---

## 7. Product roadmap

Each version is independently useful — stop after any milestone and the
preceding work still delivers value.

### v1 — Framework + AST migrator + one ported test *(this document)*

pytest plugin with fixtures, YAML config, JSON result publisher, CMW100 driver,
`openflow migrate` tool, Tx EVM Power Sweep running end-to-end against a real
CMW100. Foundation laid; one demonstrably better test as proof.
**OpenTAP dependency: removed entirely.**

### v2 — Bulk migration of the U300 EVT suite

Use the v1 converter to migrate every existing OpenTAP-Python test in the U300
RFEngine EVT suite. Manual cleanup of any TODOs the converter leaves. All tests
runnable via pytest. Adds a small HTML report renderer (one-page summary per
session, drilling down by parametrize case).

### v3 — Full instrument coverage

Drivers for SG, SA, WFG, DMM (today's UMT_Instruments equivalents), plus any
others the migrated tests need. Each driver follows the CMW100 pattern (PyVISA
+ thin SCPI wrapper). Migration tool updated as we discover new patterns.

### v4 — Persistent results

Result accumulator gains a SQLite backend (and optional PostgreSQL for shared
labs). pytest hooks emit each `results.publish(...)` row to the DB as well as
the per-session JSON. Enables historical queries and trend analysis without a
build-from-scratch dashboard.

### v5 — Lab orchestration

Bench reservation primitive, multi-DUT parallel runs via pytest-xdist,
optional web dashboard (read-only) that reads from the v4 results DB. **This
is the rough end-state** — no further versions planned unless new needs surface.

---

## 8. Open questions for the engineering reviewer

1. **UMT_Instruments / UMT_DUTs / U300_RFEngine module status** (most important).
   Are these classes plain Python (just SCPI wrappers and helpers), or do they
   inherit from `OpenTap.Instrument` / `OpenTap.Resource` with the same
   property/`@attribute` decoration as the test files? Answer determines whether
   v1 imports them as-is or has to port them too. *Recommended action: send me
   one representative file from each module (e.g. `UMT_Instruments/CMW100.py`,
   `UMT_DUTs/UMT_DUT.py`) so we can confirm.*

2. **CMW100 driver scope for v1.** The Tx EVM test uses
   `cmw100.setup_NrTx(...)`, `cmw100.meas_NrTxAll()`, `cmw100.meas_NrTxPower(use_cached=True)`,
   `cmw100.meas_NrTxEVM(use_cached=True)`. If existing `UMT_Instruments/CMW100.py`
   is plain Python, we vendor it. If not, v1 needs to ship a CMW100 driver
   covering at least those four methods — non-trivial but bounded.

3. **Verdict-pattern conversion in the migrator.** Most cases are
   `if ok: UpgradeVerdict(Pass) else: UpgradeVerdict(Fail)` → `assert ok`. But
   the Tx EVM test has a nested condition (don't fail if power exceeded MPR).
   We need an explicit decision: convert this to a `pytest.skip()` when MPR is
   exceeded, or keep as a nested `assert` with explanatory comment.

4. **YAML config schema.** The two reference tests use ~20 input parameters
   (`in_band`, `in_modulation`, `in_rfbw_Hz`, `in_dl_config_active`, etc.). v1
   must publish a documented YAML schema and validate it via pydantic. Draft
   schema is part of the v1 plan; engineer to review before implementation.

5. **Live-instrument smoke test.** v1 includes a `MockCMW100`-based integration
   test in CI. Real CMW100 smoke testing is manual on the bench. Acceptable as
   the v1 reality?

6. **Logging.** pytest captures stdout. Real RF tests run for tens of minutes
   and engineers expect to watch progress. v1 should configure `--log-cli-level=INFO`
   by default and pipe through `rich` for readable formatting. Confirm OK.

---

## 9. Project repository

- Repo: https://github.com/mayhuifu/OpenFlow (private)
- Pre-pivot C# work preserved at:
  - Tag: `v0.1.0-csharp-archived`
  - Branch: `archive/csharp-runner`
  - Old design doc lives on that branch at `docs/superpowers/specs/2026-05-21-openflow-v1-design.md`
- `main` is reset to a fresh Python project starting from this document.
- License: MIT (carried over from the C# v0.1.0).
