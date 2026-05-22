# OpenFlow Bench Bring-Up Runbook — V1c → V5

**Date:** 2026-05-23
**Target version:** v1.0.0-rc1 (or later)
**Audience:** Bench engineer on a real RF lab machine
**Time budget:** 1–2 days for V1c–V3, +1 day each for V4 + V5 (mostly automated)

---

## How to use this document

This is an **operational runbook**, not a tutorial. Each phase has:

- **Prerequisites** — what hardware + software must be ready before starting
- **Procedure** — exact commands to run, in order
- **Test cases** — labelled `TC-<phase>-<n>`, with expected pass criteria
- **Troubleshooting** — common failures and fixes
- **Sign-off** — checkbox row the engineer ticks to mark the phase complete

Phases gate each other: don't start Phase 3 (V1f DMM) before Phase 1
(V1c CMW100 connectivity) passes.

Test cases marked **CRITICAL** must pass before continuing. Test cases
marked **OPTIONAL** are informational; failure doesn't block the phase.

Throughout this doc, `<ENGINEER>` means your identifier (initials, name,
or `$USER`). `<BENCH_ID>` means the bench machine's hostname or label.

> **Adding more test cases:** This catalog is the minimum bring-up set.
> Bench engineers should add domain-specific test cases as they go — see
> [§ Adding test cases](#adding-test-cases) for the template.

---

## Table of contents

- [Phase 0: Lab machine setup](#phase-0-lab-machine-setup)
- [Phase 1: V1c — CMW100 + DUT connectivity](#phase-1-v1c--cmw100--dut-connectivity)
- [Phase 2: V1d/V1e — Migrator validation](#phase-2-v1dv1e--migrator-validation)
- [Phase 3: V1f — Keysight 34461A DMM](#phase-3-v1f--keysight-34461a-dmm)
- [Phase 4: V2 — Bulk migration + HTML reports](#phase-4-v2--bulk-migration--html-reports)
- [Phase 5: V3 — SG + SA + WFG drivers](#phase-5-v3--sg--sa--wfg-drivers)
- [Phase 6: V4 — Persistent results](#phase-6-v4--persistent-results)
- [Phase 7: V5 — Lab orchestration](#phase-7-v5--lab-orchestration)
- [Phase 8: End-to-end integration test](#phase-8-end-to-end-integration-test)
- [Test case catalog](#test-case-catalog)
- [Adding test cases](#adding-test-cases)
- [Sign-off page](#sign-off-page)

---

## Bench equipment checklist (fill in before starting)

| Item | Model | VISA resource / address | Serial # | Confirmed |
|---|---|---|---|---|
| Lab machine | _______ | hostname: _______ | n/a | ☐ |
| CMW100 | R&S CMW100 | TCPIP0::____.____.____.____ ::INSTR | _______ | ☐ |
| DMM (current) | Keysight 34461A | TCPIP0::____.____.____.____ ::INSTR | _______ | ☐ |
| DMM (voltage) | Keysight 34461A | TCPIP0::____.____.____.____ ::INSTR | _______ | ☐ |
| SG | R&S SMW200A | TCPIP0::____.____.____.____ ::INSTR | _______ | ☐ |
| SA | Keysight N9020B *or* R&S FSW | TCPIP0::____.____.____.____ ::INSTR | _______ | ☐ |
| WFG | Keysight 33500B | TCPIP0::____.____.____.____ ::INSTR | _______ | ☐ |
| U300 board | RFEB rev ___ + RFHB rev ___ | n/a | RFEB:____  RFHB:____ | ☐ |
| FTDI bridge | FT2232H | ftdi://ftdi:2232h:____/2 | _______ | ☐ |
| Cabling | RF / DC / LAN / USB | (see bench drawing) | n/a | ☐ |

---

# Phase 0: Lab machine setup

**Goal:** OpenFlow installed and the 424-test internal suite passes. No
bench instruments touched yet.

## Prerequisites

- Lab machine running Windows 10/11 or Ubuntu 22.04 LTS
- NI-VISA installed (Windows) or pyvisa-py backend reachable (Linux)
- Internet access for `uv sync` (or the offline bundle from a release)
- Engineer has shell access (PowerShell on Windows, bash on Linux)

## Procedure

### Step 0.1 — Install `uv`

```sh
# macOS / Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:
```sh
uv --version
# Expected: uv 0.4.x or later
```

### Step 0.2 — Get the OpenFlow source

**Online (preferred):**
```sh
git clone https://github.com/mayhuifu/OpenFlow.git
cd OpenFlow
git checkout v1.0.0-rc1  # or the latest tag
```

**Offline (lab machine without internet):**
```sh
# On a machine WITH internet, run the bundle script:
bash scripts/make-offline-bundle.sh --offline

# Copy dist/OpenFlow-*.zip to the lab machine. On the lab machine:
unzip OpenFlow-*.zip
cd OpenFlow
```

### Step 0.3 — Sync dependencies

```sh
uv sync
# For PostgreSQL + plotting support (optional):
uv sync --extras postgres --extras plot
```

Expected: completes without errors, ~700 MB of wheels installed.

### Step 0.4 — Smoke test the framework

```sh
uv run pytest tests-internal/
```

**Test case TC-V0-01 — Framework health check (CRITICAL):**
- **Expected:** `424 passed, 3 skipped` (the 3 are PostgreSQL tests; they skip unless you set `OPENFLOW_TEST_PG_DSN`)
- **Pass criterion:** Exit code 0, no failures
- **If it fails:** Stop. Re-run `uv sync`. Check Python version (must be ≥3.11). File an issue with the failing output.

### Step 0.5 — Confirm CLI entry points

```sh
uv run openflow --help
uv run openflow migrate --help
uv run openflow report --help
uv run openflow bench --help
uv run openflow dashboard --help
```

**Test case TC-V0-02 — CLI subcommands discoverable (CRITICAL):**
- **Expected:** Each command prints its usage without error.
- **Pass criterion:** All five commands return exit code 0.

## Sign-off

| | | |
|---|---|---|
| TC-V0-01 framework tests pass | ☐ | engineer initials: ___ |
| TC-V0-02 CLI commands discoverable | ☐ | engineer initials: ___ |
| Bench equipment checklist filled in | ☐ | engineer initials: ___ |

---

# Phase 1: V1c — CMW100 + DUT connectivity

**Goal:** Prove the LAN ↔ CMW100 ↔ R&S SDK chain works. Establish that
the NR FR1 Meas measurement chain is correctly configured. This is the
foundational phase — almost every other phase depends on the CMW100.

## Prerequisites

- Phase 0 signed off
- CMW100 powered on, LAN-reachable from the lab machine
- CMW100 firmware ≥ 3.8.17 (the version validated against in v0.4.0)
- NR FR1 Meas software option licensed on the CMW100 (verify via `*OPT?`)
- The U300 DUT board is **not yet required** for Phase 1 (Phase 1 is CMW100-only)

## Configuration

Edit `tests/configs/u300b0_evt.yaml`:

```yaml
instruments:
  cmw100:
    resource: "TCPIP0::<CMW100_IP>::INSTR"   # ← replace with bench address
```

Leave the other instruments at `MOCK::...` for now (they're tested in
later phases).

## Procedure

### Step 1.1 — VISA reachability

Before running any pytest, confirm the lab machine can reach the CMW100:

```sh
ping <CMW100_IP>
# Expected: 4 replies, < 5ms latency
```

If your machine has NI-VISA tools installed:
```
NI MAX → Devices and Interfaces → Network Devices
# Expected: CMW100 appears with status "Working"
```

### Step 1.2 — CMW100 connectivity smoke

```sh
uv run pytest tests/bench_bringup/test_01_cmw100_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/01-conn.json \
    --openflow-html-report=reports/01-conn.html \
    --log-cli-level=INFO -v
```

**Test case TC-V1C-01 — CMW100 *IDN? round-trip (CRITICAL):**
- **Expected output:**
  ```
  INFO  CMW100 *IDN? -> Rohde&Schwarz,CMW,1201.0002k06/<serial>,<firmware>
  INFO  CMW100 SYST:ERR? -> 0,"No error"
  PASSED
  ```
- **Pass criterion:** Test PASSES, `pending_errors` is empty.
- **Sign-off:** Record the `*IDN?` string in the bench equipment checklist.

### Step 1.3 — CMW100 NR diagnostics (gating)

```sh
uv run pytest tests/bench_bringup/test_02_cmw100_nr_diagnostics.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/02-diag.json \
    --log-cli-level=INFO -v
```

**Test case TC-V1C-02 — NR FR1 Meas diagnostic (CRITICAL):**
- This test **always passes** (no assertions). Read the SUMMARY block in the log.
- **Inspect:**
  - `NR options:` — must list at least one `NR`-prefixed option (e.g. `KS630NRBASE`). If empty, the CMW100 lacks the NR FR1 Meas license — escalate to bench owner.
  - `Current app:` — what `INSTrument:SELect?` returns. If it's NOT an NR app, take note of which app is active.
  - `App list:` — every available app on this CMW100.
  - `NRSub probe:` — if this returns a clean value, the NR chain is healthy.
  - `NRSub errors:` — should be empty.

**Decision matrix:**

| SUMMARY output | Diagnosis | Next step |
|---|---|---|
| NR options absent | CMW100 lacks NR FR1 Meas license | Escalate. Cannot run TC-V1C-03+. |
| NR options present, NRSub probe clean | NR chain healthy | Proceed to TC-V1C-03. |
| NR options present, NRSub returns `-114` | NR app not instantiated | Edit `openflow/instruments/cmw100.py`: add `INSTrument:CREate "NR Sub Meas Q4"` (or equivalent — name visible in `App list`) to `CMW100.open()`. Re-run TC-V1C-02. |

### Step 1.4 — CMW100 TX-EVM smoke sweep

```sh
uv run pytest tests/bench_bringup/test_03_cmw100_tx_evm_smoke.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/03-smoke.json \
    --openflow-html-report=reports/03-smoke.html \
    --log-cli-level=INFO -v
```

**Test case TC-V1C-03 — 5-point TX-EVM sweep (CRITICAL):**
- **Expected:** 5 sweep points complete; per-point `measured_tx_power_dBm` and `measured_EVM_pct` reported. NaN measurements are acceptable (means no signal at port) but the SCPI path must complete cleanly.
- **Pass criterion:** Test PASSES, no SCPI errors raised.
- **If it fails with `-114 "Header suffix out of range"`:** TC-V1C-02 wasn't fully addressed. Go back to Step 1.3.

### Step 1.5 — Optional: DUT_U300 connectivity (FTDI + SPI)

Only run this if the U300 board + FTDI bridge are wired up.

Edit `tests/configs/u300b0_evt.yaml`:

```yaml
dut:
  type: u300
  emulation: false
  ftdi_address: "ftdi://ftdi:2232h:<SERIAL>/2"
  reg_map_file: "U300_RFIC_A0_V00.csv"
```

```sh
uv run pytest -k test_dut --openflow-config=tests/configs/u300b0_evt.yaml -v
```

**Test case TC-V1C-04 — DUT_U300 instantiation (OPTIONAL):**
- **Expected:** `dut` fixture opens without crashing.
- **Known limitation:** Calling `dut.cmd_initialize()` / `set_rfTxStop` / `set_rfTxPower` raises `NotImplementedError` on real hardware — the `rfd_simulator` port wasn't bundled in V1c. Document the gap, don't try to fix in this phase.

**Test case TC-V1C-05 — DUT SPI register round-trip (OPTIONAL):**
- Use a small ad-hoc test (engineer writes ~10 lines):
  ```python
  def test_spi_read(dut):
      val = dut.read_register(0x00)  # whatever the U300 ID register is
      assert val != 0xFFFF
  ```
- **Pass criterion:** Read returns a known register value.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pyvisa.errors.VisaIOError: Could not connect` | Wrong resource string / CMW100 powered off | Verify `ping`, check CMW100 LAN config |
| `ModuleNotFoundError: No module named 'rscmw_base'` | `uv sync` didn't complete | Re-run `uv sync` |
| `pending_errors` non-empty | Stale errors from previous session | Send `*CLS` via CMW100 front panel, re-run test |
| `-114 "Header suffix out of range"` (any NR test) | NR app not instantiated | See TC-V1C-02 decision matrix |
| TC-V1C-04 raises `NotImplementedError` | DUT_U300 RFIC methods not yet ported | Expected — flag for V1g/V2 work |

## Sign-off

| | | |
|---|---|---|
| TC-V1C-01 CMW100 *IDN? PASS | ☐ | initials: ___ |
| TC-V1C-02 NR diagnostic reviewed | ☐ | initials: ___ |
| TC-V1C-03 TX-EVM smoke PASS | ☐ | initials: ___ |
| TC-V1C-04 DUT_U300 instantiation (if attempted) | ☐ | initials: ___ |
| TC-V1C-05 DUT SPI round-trip (if attempted) | ☐ | initials: ___ |
| **Phase 1 sign-off** | ☐ | initials: ___ + date: ___ |

---

# Phase 2: V1d/V1e — Migrator validation

**Goal:** Confirm the 22-stage libcst migrator produces runnable output
against at least one OpenTAP-Python test source file from the engineer's
existing test suite.

## Prerequisites

- Phase 0 signed off
- Engineer has **at least one** OpenTAP-Python test source file from
  the U300 EVT suite (e.g. `U300B0_RFEB_EVT_RX_Gain_Accuracy.py`).
  Note: no bench instruments are needed for this phase — pure code work.

## Procedure

### Step 2.1 — Verify migrator on canonical fixture

Sanity check that the migrator produces the expected output against the
canonical fixture shipped in the repo:

```sh
uv run openflow migrate tests-internal/fixtures/sample_opentap_tx_evm.py
# Output: tests-internal/fixtures/test_sample_opentap_tx_evm.py
```

**Test case TC-V1DE-01 — Canonical fixture migrates cleanly (CRITICAL):**
- **Expected:** Output file is created. The CLI prints:
  ```
  wrote tests-internal/fixtures/test_sample_opentap_tx_evm.py
    test signature uses fixtures: ['cmw100', 'wfg', 'dut', 'dmm_c', 'dmm_v']
    PublishResult calls were left bare — pick out_* values to forward to results.publish()
  ```
- **Pass criterion:** File is created. Grep for these markers (all should appear):
  ```sh
  grep -E "CLASS_NAME = |setup_dmm\(dmms=|config\.limits_path|@pytest\.mark\.parametrize" \
       tests-internal/fixtures/test_sample_opentap_tx_evm.py
  ```
- **Clean up:** Delete the output file before running tests-internal/ — it would otherwise be picked up by pytest.

### Step 2.2 — Migrate engineer-provided EVT source

Copy your OpenTAP source file into `tests-internal/fixtures/` (or any
working directory):

```sh
cp /path/to/U300B0_RFEB_EVT_RX_Gain_Accuracy.py /tmp/
uv run openflow migrate /tmp/U300B0_RFEB_EVT_RX_Gain_Accuracy.py \
    -o /tmp/test_rx_gain_accuracy.py
```

**Test case TC-V1DE-02 — Real EVT source migrates (CRITICAL):**
- **Expected:** Output file created, no exceptions raised.
- **Pass criterion:** File created. CLI does NOT print "transformer failed" or similar.

### Step 2.3 — Inspect migrator output

```sh
cat /tmp/test_rx_gain_accuracy.py
```

**Test case TC-V1DE-03 — Migrated test inspection (OPTIONAL but recommended):**
- **Check for residual OpenTAP traces (should NOT appear):**
  - `import OpenTap`
  - `from opentap import *`
  - `@attribute(OpenTap.Display(...))`
  - `self.UpgradeVerdict(`
  - `self.PublishResult(`
  - `self.log.Info(`
  - `__class__.__name__` (bare, without the `CLASS_NAME =` definition)
- **Check that V2 transformers fired (should appear when applicable):**
  - `@pytest.mark.parametrize` (if the source had a simple sweep loop)
  - `logger.info("Print_Summary:` (if the source had `Print_Summary()` calls)
  - `from openflow.rfengine.evt_base import setup_dmm` (if source called `Setup_DMM`)
- **Document gaps** in `docs/v2-bulk-migration-guide.md` (created in V2 spec): which patterns did the migrator NOT handle? Each gap is a candidate for a new transformer.

### Step 2.4 — Collect the migrated test

Without running on real bench, just confirm the migrated file is valid Python:

```sh
uv run python -c "import ast; ast.parse(open('/tmp/test_rx_gain_accuracy.py').read())"
uv run pytest /tmp/test_rx_gain_accuracy.py --collect-only
```

**Test case TC-V1DE-04 — Migrated test collects (CRITICAL):**
- **Expected:** pytest collects 1+ tests. Some may need `--openflow-config` to fully resolve; collection alone is the test.
- **Pass criterion:** No `SyntaxError`. Collection prints test node IDs.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `SyntaxError` in migrated output | Migrator pattern not yet handled | File a bug with the source file + line number. Hand-edit the output for now. |
| `NameError` at collection time | Engineer-specific helper not imported | Add the import manually OR open a V1g/V2 transformer issue for the pattern. |
| Original `self.X` traces in output | A transformer skipped the file | Check `openflow/migrate/pipeline.py` — file an issue with a 5-line repro. |

## Sign-off

| | | |
|---|---|---|
| TC-V1DE-01 canonical fixture migrates | ☐ | initials: ___ |
| TC-V1DE-02 engineer's EVT source migrates | ☐ | initials: ___ |
| TC-V1DE-03 output inspected; gaps documented | ☐ | initials: ___ |
| TC-V1DE-04 migrated test collects | ☐ | initials: ___ |
| **Phase 2 sign-off** | ☐ | initials: ___ + date: ___ |

---

# Phase 3: V1f — Keysight 34461A DMM

**Goal:** Prove the LAN ↔ DMM ↔ pyvisa chain works for both current
(`dmm_c`) and voltage (`dmm_v`) DMM fixtures.

## Prerequisites

- Phase 0 signed off (Phase 1/2 not strictly required, but recommended)
- Keysight 34461A DMM(s) powered on, LAN-reachable
- LAN/SCPI enabled on the DMM (default port 5025)

## Configuration

Edit `tests/configs/u300b0_evt.yaml`:

```yaml
instruments:
  dmm_c:
    resource: "TCPIP0::<DMM_C_IP>::INSTR"
  dmm_v:
    resource: "TCPIP0::<DMM_V_IP>::INSTR"   # optional — only if you have two DMMs
```

## Procedure

### Step 3.1 — VISA reachability

```sh
ping <DMM_C_IP>
# Expected: 4 replies, low latency
```

### Step 3.2 — DMM connectivity smoke

```sh
uv run pytest tests/bench_bringup/test_04_dmm_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/04-dmm.json \
    --log-cli-level=INFO -v
```

**Test case TC-V1F-01 — DMM_C *IDN? round-trip (CRITICAL):**
- **Expected output:**
  ```
  INFO  DMM (dmm_c) *IDN? -> Keysight Technologies,34461A,<serial>,<firmware>
  INFO  DMM (dmm_c) error queue -> <clean>
  PASSED
  ```
- **Pass criterion:** Test PASSES, error queue empty.

### Step 3.3 — Manual DMM measurement smoke (informal)

This isn't a packaged test — it's a 5-line REPL check to confirm the DMM
actually measures, not just identifies:

```sh
uv run python
```

```python
>>> from openflow.instruments.dmm_keysight import DMMKeysight34461A
>>> dmm = DMMKeysight34461A("TCPIP0::<DMM_C_IP>::INSTR", is_emulation=False)
>>> dmm.open()
>>> dmm.set_mode(isVoltage=False, isDc=True)
>>> dmm.set_range_current(1.0)  # 1 A range
>>> dmm.get_measurement()
0.00012345  # whatever the actual current is at the DMM input
>>> dmm.close()
```

**Test case TC-V1F-02 — DMM live measurement (CRITICAL):**
- **Pass criterion:** `get_measurement()` returns a finite float. Order
  of magnitude should match the actual current/voltage at the DMM input
  (use a known DC source if you have one — e.g. a battery, a current
  source).

### Step 3.4 — DMM voltage mode (OPTIONAL)

If `dmm_v` is wired:

**Test case TC-V1F-03 — DMM voltage mode (OPTIONAL):**
```python
>>> dmm_v.set_mode(isVoltage=True, isDc=True)
>>> dmm_v.set_range_voltage(10.0)
>>> dmm_v.get_measurement()
```
- **Pass criterion:** Returns a finite voltage value matching the input.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pyvisa.errors.VisaIOError: VI_ERROR_RSRC_NFOUND` | DMM IP not in NI MAX / pyvisa-py | Add resource manually, or use `TCPIP0::<IP>::5025::SOCKET` format |
| `*IDN?` returns wrong model | Different DMM at that IP | Update `_IDN_HINT` if model differs significantly OR subclass the driver |
| `get_measurement()` returns NaN | DMM didn't trigger | Check that `set_mode` ran first; check CONF: setting on DMM front panel |
| `NotImplementedError: AC current` | Engineer called `set_mode(isDc=False)` | AC paths are deferred to V2/V3. Use DC for now. |

## Sign-off

| | | |
|---|---|---|
| TC-V1F-01 DMM *IDN? PASS | ☐ | initials: ___ |
| TC-V1F-02 DMM live measurement | ☐ | initials: ___ |
| TC-V1F-03 DMM voltage (if applicable) | ☐ | initials: ___ |
| **Phase 3 sign-off** | ☐ | initials: ___ + date: ___ |

---

# Phase 4: V2 — Bulk migration + HTML reports

**Goal:** Validate the HTML report renderer produces a useful artifact;
migrate 1–2 additional EVT tests beyond Phase 2's first one.

## Prerequisites

- Phase 1 signed off (CMW100 connectivity proven)
- Phase 2 signed off (migrator works on at least one EVT source)

## Procedure

### Step 4.1 — Generate HTML report from existing bench bring-up runs

```sh
uv run pytest tests/bench_bringup/ \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/bringup-full.json \
    --openflow-html-report=reports/bringup-full.html \
    --log-cli-level=INFO -v
```

**Test case TC-V2-01 — HTML report renders (CRITICAL):**
- **Expected:** `reports/bringup-full.html` created. Open in a browser.
- **Pass criterion:**
  - File opens without "missing asset" errors (single-file constraint)
  - Summary band shows passed/failed counts
  - Each bring-up test appears as a row
  - For tests with multi-record measurements, inline SVG sparklines render
  - File size < 100 KB

### Step 4.2 — Email-share test

Email the `bringup-full.html` to yourself / a colleague. Verify it opens
without any external asset fetches.

**Test case TC-V2-02 — HTML report self-contained (CRITICAL):**
- **Expected:** Recipient opens the email attachment offline (e.g. disable WiFi first). Report renders identically.
- **Pass criterion:** No broken images / unstyled output / missing JS.

### Step 4.3 — Migrate 1–2 additional EVT tests

Pick the next 1–2 most-important tests from your existing OpenTAP suite
(e.g. RX Gain Accuracy + TX ACLR). Repeat the Phase 2 procedure for each.

**Test case TC-V2-03 — Second EVT test migrates + collects (CRITICAL):**
- Same criteria as TC-V1DE-02 and TC-V1DE-04, applied to the second source.
- **Pass criterion:** Both tests' migrated files collect cleanly.

### Step 4.4 — Surface new migrator patterns

For each new test, inspect the output for residual hand-edits the
migrator didn't handle. Each unique pattern is a candidate for a new
transformer.

**Test case TC-V2-04 — Pattern inventory (OPTIONAL):**
- Add findings to `docs/v2-bulk-migration-guide.md` under "Patterns surfaced during bulk migration."
- For each pattern, decide: (a) write a new transformer, (b) leave manual.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| HTML report empty (no test rows) | No tests ran (collection-only) or no `results.publish()` calls | Make sure the test bodies use `results.publish(...)` for measurements |
| HTML report > 100 KB | Too many sweep records per test | Reduce sweep range, or accept the size (still < 1 MB in practice) |
| New EVT migration has `NameError: 'X'` at collect | Engineer-specific helper not imported by migrator | Add the import manually or extend `RewriteImportPaths` |

## Sign-off

| | | |
|---|---|---|
| TC-V2-01 HTML report renders | ☐ | initials: ___ |
| TC-V2-02 HTML report self-contained | ☐ | initials: ___ |
| TC-V2-03 second EVT test migrates | ☐ | initials: ___ |
| TC-V2-04 pattern inventory (if done) | ☐ | initials: ___ |
| **Phase 4 sign-off** | ☐ | initials: ___ + date: ___ |

---

# Phase 5: V3 — SG + SA + WFG drivers

**Goal:** Validate the three new V3 instrument drivers against real
hardware. Each is independent of the others — you can run them in any
order.

## Prerequisites

- Phase 0 signed off
- R&S SMW200A signal generator powered on + LAN-reachable
- Keysight N9020B MXA *or* R&S FSW spectrum analyzer powered on + LAN-reachable
- Keysight 33500B waveform generator powered on + LAN-reachable

## Configuration

Edit `tests/configs/u300b0_evt.yaml`:

```yaml
instruments:
  sg:
    resource: "TCPIP0::<SG_IP>::INSTR"
    # model: rs_smw200a              # default
  sa:
    resource: "TCPIP0::<SA_IP>::INSTR"
    model: keysight_n9020b           # or rs_fsw if using R&S
  wfg:
    resource: "TCPIP0::<WFG_IP>::INSTR"
    # model: keysight_33500b         # default
```

## Procedure

### Step 5.1 — Signal generator bring-up

```sh
uv run pytest tests/bench_bringup/test_05_sg_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/05-sg.json \
    --openflow-html-report=reports/05-sg.html \
    --log-cli-level=INFO -v
```

**Test case TC-V3-01 — SG *IDN? round-trip (CRITICAL):**
- **Expected:** `SG *IDN? -> Rohde&Schwarz,SMW200A,...` + clean error queue.
- **Pass criterion:** Test PASSES.

**Test case TC-V3-02 — SG output control (CRITICAL):**
Open a Python REPL:
```python
>>> from openflow.instruments.sg_rs_smw200a import RsSmw200a
>>> sg = RsSmw200a("TCPIP0::<SG_IP>::INSTR", is_emulation=False)
>>> sg.open()
>>> sg.set_frequency(2.5e9)
>>> sg.set_rf_power(-30.0)
>>> sg.output_on()
# At this point, verify on the SG's front panel that frequency = 2.5 GHz,
# power = -30 dBm, RF output enabled.
>>> sg.output_off()
>>> sg.close()
```
- **Pass criterion:** SG front panel reflects the commands.

### Step 5.2 — Spectrum analyzer bring-up

```sh
uv run pytest tests/bench_bringup/test_06_sa_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/06-sa.json \
    --openflow-html-report=reports/06-sa.html \
    --log-cli-level=INFO -v
```

**Test case TC-V3-03 — SA *IDN? round-trip (CRITICAL):**
- **Expected:** Either `SA *IDN? -> Keysight Technologies,N9020B,...` (default) or `SA *IDN? -> Rohde&Schwarz,FSW,...` (if `model: rs_fsw`).
- **Pass criterion:** Test PASSES.

**Test case TC-V3-04 — SA marker peak measurement (CRITICAL):**
Connect the SG output (TC-V3-02) to the SA input via attenuator (verify safe levels first). Then:
```python
>>> # SG sends -30 dBm CW at 2.5 GHz
>>> sg.set_frequency(2.5e9); sg.set_rf_power(-30); sg.output_on()
>>>
>>> from openflow.instruments.sa_keysight_n9020b import KeysightN9020B
>>> sa = KeysightN9020B("TCPIP0::<SA_IP>::INSTR", is_emulation=False)
>>> sa.open()
>>> sa.set_center_frequency(2.5e9)
>>> sa.set_span(1e6)
>>> sa.set_reference_level(-20.0)
>>> sa.trigger_sweep()
>>> freq, power = sa.meas_marker_peak()
>>> print(f"peak: {freq/1e9} GHz at {power} dBm")
peak: 2.5 GHz at -30.3 dBm   # ← real reading should be within 1-2 dB of -30
```
- **Pass criterion:** Returned `freq` is within ±10 kHz of 2.5 GHz; `power` is within ±2 dB of -30 (assuming 0 attenuation).

### Step 5.3 — Waveform generator bring-up

```sh
uv run pytest tests/bench_bringup/test_07_wfg_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/07-wfg.json \
    --openflow-html-report=reports/07-wfg.html \
    --log-cli-level=INFO -v
```

**Test case TC-V3-05 — WFG *IDN? round-trip (CRITICAL):**
- **Expected:** `WFG *IDN? -> Keysight Technologies,33522B,...` (or whichever 33500B variant).
- **Pass criterion:** Test PASSES.

**Test case TC-V3-06 — WFG output enable (CRITICAL):**
```python
>>> from openflow.instruments.wfg_keysight_33500b import Keysight33500B
>>> wfg = Keysight33500B("TCPIP0::<WFG_IP>::INSTR", is_emulation=False)
>>> wfg.open()
>>> wfg.set_arb_sample_rate(1e6, channel=1)
>>> wfg.set_arb_output_amplitude_Vpp(0.5, channel=1)
>>> wfg.output_on(channel=1)
# Verify on the WFG front panel: channel 1 output is on, ~0.5 Vpp.
>>> wfg.output_off(channel=1)
>>> wfg.close()
```
- **Pass criterion:** WFG front panel reflects the commands.

### Step 5.4 — Multi-instrument integration

This is the V3b validation gate: prove that SG + SA + WFG + CMW100 +
DMM all coexist in a single pytest session without VISA-port contention
or driver-side state leaks.

**Test case TC-V3-07 — All-instrument fixture resolution (CRITICAL):**
Write a small ad-hoc test:
```python
# tests/test_v3_integration.py
def test_all_instruments_open(cmw100, sg, sa, wfg, dmm_c):
    assert cmw100.identify()
    assert "SMW200A" in sg.identify()
    assert "N9020B" in sa.identify() or "FSW" in sa.identify()
    assert "33" in wfg.identify()  # 33522B / 33510B / 33509B etc
    assert "34461A" in dmm_c.identify()
```

```sh
uv run pytest tests/test_v3_integration.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --log-cli-level=INFO -v
```

- **Pass criterion:** Test PASSES. No VISA resource conflicts. All 5
  instruments respond to `*IDN?`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| SG commands don't change anything visible | SG in remote-locked mode | Press `Local` on SG front panel after each test session (or send `SYST:LOCK 0`) |
| SA peak power off by >5 dB | Reference level not set correctly | Re-run `set_reference_level()` — N9020B defaults can be off |
| SA peak frequency off by >1 MHz | SG and SA on different freq references | Sync them via the 10 MHz ref out / in connectors |
| WFG output amplitude wrong | Termination impedance mismatch | Send `OUTPut:LOAD INF` if open-circuit, `50` if 50Ω term |
| TC-V3-07 hangs | One instrument's session blocks others | Verify each instrument's session opens individually first |

## Sign-off

| | | |
|---|---|---|
| TC-V3-01 SG *IDN? PASS | ☐ | initials: ___ |
| TC-V3-02 SG output control verified | ☐ | initials: ___ |
| TC-V3-03 SA *IDN? PASS | ☐ | initials: ___ |
| TC-V3-04 SA marker peak measurement | ☐ | initials: ___ |
| TC-V3-05 WFG *IDN? PASS | ☐ | initials: ___ |
| TC-V3-06 WFG output enable verified | ☐ | initials: ___ |
| TC-V3-07 all-instrument integration | ☐ | initials: ___ |
| **Phase 5 sign-off** | ☐ | initials: ___ + date: ___ |

---

# Phase 6: V4 — Persistent results

**Goal:** Validate the V4 persistent-results pipeline writes a queryable
SQLite database alongside each test session, and the CLI surfaces
useful queries.

## Prerequisites

- Phase 1 + Phase 3 + Phase 5 signed off (need real test sessions to
  populate the DB with meaningful data)

## Configuration

Edit `tests/configs/u300b0_evt.yaml`:

```yaml
storage:
  persist: true
  # sqlite_path: /var/lib/openflow/report.db  # optional; defaults to ./report.db
  # postgres_dsn: postgresql://...           # optional; off by default
```

## Procedure

### Step 6.1 — Run a test session with persistence enabled

```sh
uv run pytest tests/bench_bringup/test_03_cmw100_tx_evm_smoke.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/03-smoke.json \
    --log-cli-level=INFO -v
```

**Test case TC-V4-01 — Sibling report.db is created (CRITICAL):**
- **Expected:** `reports/report.db` exists alongside `reports/03-smoke.json`.
- **Pass criterion:**
  ```sh
  ls -la reports/report.db
  # Non-zero size
  ```

### Step 6.2 — Query the database via CLI

```sh
uv run openflow report --db reports/report.db list-sessions
uv run openflow report --db reports/report.db query
uv run openflow report --db reports/report.db query --where "testcase_id LIKE 'CMW100%'"
```

**Test case TC-V4-02 — Query CLI returns expected rows (CRITICAL):**
- **Expected:**
  - `list-sessions` shows 1 session (the one you just ran)
  - `query` (no filter) shows the 5 sweep tests
  - `query --where` filters correctly
- **Pass criterion:** Each command returns exit 0 and the table is non-empty.

### Step 6.3 — Ingest archived JSON reports

If you have older `report.json` files from V1-V3 bench runs, ingest them:

```sh
uv run openflow report --db reports/report.db ingest reports/old-runs/*.json
```

**Test case TC-V4-03 — Historical JSON ingest (OPTIONAL):**
- **Pass criterion:** Each ingest prints `ingested <path> -> session_id=...`.
- **Verify:** `list-sessions` now shows historical + new sessions.

### Step 6.4 — Trend a metric over multiple runs

Run the TX-EVM smoke test 3–5 times (with `storage.persist: true`):

```sh
for i in 1 2 3 4 5; do
  uv run pytest tests/bench_bringup/test_03_cmw100_tx_evm_smoke.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/03-smoke-run${i}.json
  sleep 30  # so timestamps differ
done

uv run openflow report --db reports/report.db trend \
    --test CMW100-TX-EVM-SMOKE \
    --metric measured_EVM_pct
```

**Test case TC-V4-04 — Trend query renders data (CRITICAL):**
- **Expected:** Table of (started_at, value) rows. ≥5 rows.
- **Pass criterion:** Table shows EVM values across multiple runs.

### Step 6.5 — Optional: matplotlib plot

```sh
uv sync --extras plot
uv run openflow report --db reports/report.db trend \
    --test CMW100-TX-EVM-SMOKE \
    --metric measured_EVM_pct \
    --plot trend.png
```

**Test case TC-V4-05 — Trend plot renders (OPTIONAL):**
- **Pass criterion:** `trend.png` exists and shows the metric over time.

### Step 6.6 — Optional: PostgreSQL backend

Only if your lab has a shared Postgres instance:

```yaml
storage:
  persist: true
  postgres_dsn: "postgresql://openflow:<password>@<host>:5432/openflow"
```

```sh
uv sync --extras postgres
# Run any test; the plugin writes to both SQLite and Postgres.
```

**Test case TC-V4-06 — PostgreSQL shared write (OPTIONAL):**
- **Pass criterion:** Test run produces local SQLite AND inserts a row into the shared Postgres `sessions` table.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| No `report.db` created | `storage.persist: false` in YAML | Set to `true` |
| `report.db` exists but is empty | Test session had 0 publishes | Check the test body uses `results.publish(...)` |
| `query --where` syntax error | SQL fragment has bad quoting | Use single quotes for string literals: `--where "testcase_id LIKE 'X%'"` |
| Postgres write fails silently | DSN unreachable / wrong creds | Check `--log-cli-level=DEBUG` output; the warning is logged not raised |

## Sign-off

| | | |
|---|---|---|
| TC-V4-01 sibling report.db created | ☐ | initials: ___ |
| TC-V4-02 query CLI returns rows | ☐ | initials: ___ |
| TC-V4-03 historical JSON ingest | ☐ | initials: ___ |
| TC-V4-04 trend query renders data | ☐ | initials: ___ |
| TC-V4-05 plot (if used) | ☐ | initials: ___ |
| TC-V4-06 PostgreSQL (if used) | ☐ | initials: ___ |
| **Phase 6 sign-off** | ☐ | initials: ___ + date: ___ |

---

# Phase 7: V5 — Lab orchestration

**Goal:** Validate bench reservation (V5a), parallel coordinator (V5b),
and read-only dashboard (V5c).

## Prerequisites

- Phase 6 signed off (V4 DB working — V5a + V5c use it)
- For V5a/V5c: single-engineer test is enough; full multi-engineer
  test requires a colleague
- For V5b: multiple DUTs wired up — OPTIONAL (only relevant if your
  bench has >1 DUT)

## Procedure — V5a: Bench reservation

### Step 7.1 — Reserve a bench resource

```sh
uv run openflow bench reserve \
    --resource "TCPIP0::<CMW100_IP>::INSTR" \
    --for 1h \
    --reason "TX EVM baseline calibration" \
    --by <ENGINEER>
```

**Test case TC-V5-01 — Reserve CLI works (CRITICAL):**
- **Expected:** `reserved TCPIP0::<CMW100_IP>::INSTR for <ENGINEER> until <timestamp>`
- **Pass criterion:** Exit 0, file `~/.openflow/reservations.json` exists.

### Step 7.2 — List active reservations

```sh
uv run openflow bench status
```

**Test case TC-V5-02 — Status shows the reservation (CRITICAL):**
- **Expected:** Table with 1 row showing your reservation.
- **Pass criterion:** Resource string + your name + expiry appear.

### Step 7.3 — Conflict simulation

Either: (a) have a colleague try to reserve the same resource as a different user; or (b) simulate by passing a different `--by`:

```sh
uv run openflow bench reserve \
    --resource "TCPIP0::<CMW100_IP>::INSTR" \
    --for 1h --by other-engineer
# Expected: exit 1, "conflict: ... reserved by <ENGINEER>"
```

**Test case TC-V5-03 — Conflict detection (CRITICAL):**
- **Pass criterion:** Exit code 1. Conflict message names the current reserver.

### Step 7.4 — Plugin-enforced reservation check

Enable in YAML:

```yaml
bench:
  check_reservations: true
  user: <ENGINEER>
```

```sh
# Should pass (you hold the reservation):
uv run pytest tests/bench_bringup/test_01_cmw100_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml -v

# Have a colleague edit bench.user to their name and try the same:
# Should fail at sessionstart with a clear "reserved by <ENGINEER>" message.
```

**Test case TC-V5-04 — Pytest fails fast on reservation conflict (CRITICAL):**
- **Pass criterion:** When `bench.user` doesn't match the reservation holder, pytest exits with code 1 before any test runs. Output names the holder + expiry.

### Step 7.5 — Force-reserve override

```sh
uv run pytest tests/bench_bringup/test_01_cmw100_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-force-reserve -v
# Expected: warning logged about override; test runs.
```

**Test case TC-V5-05 — Force-reserve unblocks (CRITICAL):**
- **Pass criterion:** Test runs. Log contains `V5a force-reserve override`.

### Step 7.6 — Release

```sh
uv run openflow bench release --resource "TCPIP0::<CMW100_IP>::INSTR"
uv run openflow bench status
# Expected: "(no reservations)"
```

## Procedure — V5c: Read-only dashboard

### Step 7.7 — Launch the dashboard

```sh
uv run openflow dashboard serve --db reports/report.db --host 127.0.0.1 --port 8080
# In another terminal, or in a browser:
```

Open `http://127.0.0.1:8080/` in a browser.

**Test case TC-V5-06 — Dashboard home renders (CRITICAL):**
- **Expected:** The home page shows recent sessions (from Phase 6 runs).
- **Pass criterion:** No 500 errors. Sessions list visible.

### Step 7.8 — Browse session detail

Click on a session ID from the home page.

**Test case TC-V5-07 — Session detail page (CRITICAL):**
- **Expected:** Page shows session metadata + per-test rows.
- **Pass criterion:** All 5 TX-EVM tests visible.

### Step 7.9 — Bench reservations view

Reserve a resource (TC-V5-01), then navigate to `/bench`.

**Test case TC-V5-08 — Dashboard bench view (CRITICAL):**
- **Expected:** Active reservation appears in the table.
- **Pass criterion:** Resource + reserver + expiry visible.

### Step 7.10 — Trend view

Navigate to `/trends`. Fill in the form with `test=CMW100-TX-EVM-SMOKE`, `metric=measured_EVM_pct`. Submit.

**Test case TC-V5-09 — Dashboard trend renders (CRITICAL):**
- **Expected:** Inline SVG chart of EVM over time.
- **Pass criterion:** Chart appears + data table below.

### Step 7.11 — JSON API for integrations

```sh
curl http://127.0.0.1:8080/api/sessions
curl http://127.0.0.1:8080/api/bench
```

**Test case TC-V5-10 — JSON API endpoints (CRITICAL):**
- **Expected:** Valid JSON responses, HTTP 200.
- **Pass criterion:** `jq .` parses the output cleanly.

### Step 7.12 — Confirm no write endpoints

```sh
curl -X POST http://127.0.0.1:8080/bench
curl -X DELETE http://127.0.0.1:8080/sessions/anything
# Both should return 405 Method Not Allowed.
```

**Test case TC-V5-11 — No write endpoints (CRITICAL):**
- **Pass criterion:** All POST/PUT/DELETE/PATCH requests return HTTP 405.

## Procedure — V5b: Multi-DUT parallel (OPTIONAL)

Only relevant if your bench has multiple DUTs wired up.

### Step 7.13 — Configure parallel DUTs

```yaml
parallel:
  duts:
    - tag: dut_1
      type: u300
      ftdi_address: "ftdi://ftdi:2232h:<SERIAL_1>/2"
      reg_map_file: "U300_RFIC_A0_V00.csv"
    - tag: dut_2
      type: u300
      ftdi_address: "ftdi://ftdi:2232h:<SERIAL_2>/2"
      reg_map_file: "U300_RFIC_A0_V00.csv"
  shared_instruments:
    - cmw100
```

**Test case TC-V5-12 — Coordinator file-locks (OPTIONAL):**
- This is exercised by the internal test suite. On real hardware, the scheduler-side wiring (1 xdist worker per DUT) lands in v1.0.0-rc2 if needed. For now, the Coordinator class is validated in CI but not yet driving real parallel runs.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `openflow bench reserve` writes nothing | Permissions on `~/.openflow/` | `mkdir -p ~/.openflow && chmod u+rwx ~/.openflow` |
| Dashboard returns 503 on /sessions | `--db` path doesn't exist | Confirm `reports/report.db` was created in Phase 6 |
| Dashboard port already in use | Another service on 8080 | Pass `--port <other>` |
| Reservation persists after engineer is gone | Filelock-only, no auto-release | Use shorter `--for` durations; or release explicitly |

## Sign-off

| | | |
|---|---|---|
| TC-V5-01 reserve CLI | ☐ | initials: ___ |
| TC-V5-02 status CLI | ☐ | initials: ___ |
| TC-V5-03 conflict detection | ☐ | initials: ___ |
| TC-V5-04 pytest reservation check | ☐ | initials: ___ |
| TC-V5-05 force-reserve override | ☐ | initials: ___ |
| TC-V5-06 dashboard home | ☐ | initials: ___ |
| TC-V5-07 session detail page | ☐ | initials: ___ |
| TC-V5-08 dashboard bench view | ☐ | initials: ___ |
| TC-V5-09 dashboard trend | ☐ | initials: ___ |
| TC-V5-10 JSON API | ☐ | initials: ___ |
| TC-V5-11 no write endpoints | ☐ | initials: ___ |
| TC-V5-12 multi-DUT coordinator (if applicable) | ☐ | initials: ___ |
| **Phase 7 sign-off** | ☐ | initials: ___ + date: ___ |

---

# Phase 8: End-to-end integration test

**Goal:** A single 1-hour bench session that exercises every V1-V5
surface together.

## Procedure

```sh
# 1. Reserve the bench (V5a)
uv run openflow bench reserve \
    --resource "TCPIP0::<CMW100_IP>::INSTR" \
    --for 2h --reason "v1.0 integration sign-off"

# 2. Start the dashboard in another terminal (V5c)
uv run openflow dashboard serve --db reports/report.db --port 8080 &

# 3. Run the full bench bring-up suite (V1c + V1f + V3) with HTML + DB persistence (V2 + V4)
uv run pytest tests/bench_bringup/ \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=reports/integration.json \
    --openflow-html-report=reports/integration.html \
    --log-cli-level=INFO -v

# 4. View the result in the dashboard
open http://localhost:8080/

# 5. Query the DB (V4)
uv run openflow report --db reports/report.db list-sessions
uv run openflow report --db reports/report.db trend \
    --test CMW100-TX-EVM-SMOKE --metric measured_EVM_pct

# 6. Release the reservation (V5a)
uv run openflow bench release --resource "TCPIP0::<CMW100_IP>::INSTR"

# 7. Stop the dashboard
kill %1
```

**Test case TC-INT-01 — End-to-end smoke (CRITICAL):**
- **Pass criterion:** All 7 steps complete without error. Engineer
  reviews the HTML report + dashboard view + DB query output and confirms
  the data is consistent.

## Sign-off

| | | |
|---|---|---|
| TC-INT-01 end-to-end smoke passes | ☐ | initials: ___ |
| **v1.0 bring-up sign-off** | ☐ | initials: ___ + date: ___ |

---

# Test case catalog

Master list — bench engineer ticks off as they go.

## Phase 0 — Lab machine setup

| ID | Description | Type |
|---|---|---|
| TC-V0-01 | 424 internal tests pass | CRITICAL |
| TC-V0-02 | All 5 CLI subcommands discoverable | CRITICAL |

## Phase 1 — V1c CMW100 + DUT

| ID | Description | Type |
|---|---|---|
| TC-V1C-01 | CMW100 `*IDN?` round-trip | CRITICAL |
| TC-V1C-02 | NR FR1 Meas diagnostic (gating) | CRITICAL |
| TC-V1C-03 | 5-point TX-EVM smoke sweep | CRITICAL |
| TC-V1C-04 | DUT_U300 instantiation | OPTIONAL |
| TC-V1C-05 | DUT SPI register round-trip | OPTIONAL |

## Phase 2 — V1d/V1e migrator validation

| ID | Description | Type |
|---|---|---|
| TC-V1DE-01 | Canonical fixture migrates cleanly | CRITICAL |
| TC-V1DE-02 | Engineer's EVT source migrates | CRITICAL |
| TC-V1DE-03 | Output inspection / gap documentation | OPTIONAL |
| TC-V1DE-04 | Migrated test collects via pytest | CRITICAL |

## Phase 3 — V1f DMM

| ID | Description | Type |
|---|---|---|
| TC-V1F-01 | DMM `*IDN?` round-trip | CRITICAL |
| TC-V1F-02 | DMM live measurement | CRITICAL |
| TC-V1F-03 | DMM voltage mode (if dmm_v wired) | OPTIONAL |

## Phase 4 — V2 HTML reports + bulk migration

| ID | Description | Type |
|---|---|---|
| TC-V2-01 | HTML report renders | CRITICAL |
| TC-V2-02 | HTML report self-contained (email test) | CRITICAL |
| TC-V2-03 | Second EVT test migrates + collects | CRITICAL |
| TC-V2-04 | Pattern inventory | OPTIONAL |

## Phase 5 — V3 SG / SA / WFG

| ID | Description | Type |
|---|---|---|
| TC-V3-01 | SG `*IDN?` round-trip | CRITICAL |
| TC-V3-02 | SG output control verified at front panel | CRITICAL |
| TC-V3-03 | SA `*IDN?` round-trip | CRITICAL |
| TC-V3-04 | SA marker peak vs SG CW | CRITICAL |
| TC-V3-05 | WFG `*IDN?` round-trip | CRITICAL |
| TC-V3-06 | WFG output enable verified at front panel | CRITICAL |
| TC-V3-07 | All-instrument fixture resolution | CRITICAL |

## Phase 6 — V4 persistent results

| ID | Description | Type |
|---|---|---|
| TC-V4-01 | Sibling `report.db` is created | CRITICAL |
| TC-V4-02 | Query CLI returns rows | CRITICAL |
| TC-V4-03 | Historical JSON ingest | OPTIONAL |
| TC-V4-04 | Trend query renders data | CRITICAL |
| TC-V4-05 | Trend plot (matplotlib) | OPTIONAL |
| TC-V4-06 | PostgreSQL shared write | OPTIONAL |

## Phase 7 — V5 lab orchestration

| ID | Description | Type |
|---|---|---|
| TC-V5-01 | Reserve CLI works | CRITICAL |
| TC-V5-02 | Status CLI shows reservation | CRITICAL |
| TC-V5-03 | Conflict detection | CRITICAL |
| TC-V5-04 | Pytest fails fast on reservation conflict | CRITICAL |
| TC-V5-05 | `--openflow-force-reserve` override | CRITICAL |
| TC-V5-06 | Dashboard home page renders | CRITICAL |
| TC-V5-07 | Session detail page | CRITICAL |
| TC-V5-08 | Dashboard bench reservations view | CRITICAL |
| TC-V5-09 | Dashboard trend view (inline SVG) | CRITICAL |
| TC-V5-10 | JSON API endpoints | CRITICAL |
| TC-V5-11 | No write endpoints (read-only constraint) | CRITICAL |
| TC-V5-12 | Multi-DUT coordinator (if multiple DUTs) | OPTIONAL |

## Phase 8 — End-to-end integration

| ID | Description | Type |
|---|---|---|
| TC-INT-01 | End-to-end smoke through all 5 phases | CRITICAL |

---

# Adding test cases

This catalog is the **minimum** bring-up set. Bench engineers should add
domain-specific test cases as they go.

## Template

```markdown
**Test case TC-<phase>-<n> — <short description> (CRITICAL / OPTIONAL):**

- **Prerequisites:** <what must be set up first>
- **Procedure:**
  ```sh
  <exact commands>
  ```
- **Expected:** <what the engineer should see>
- **Pass criterion:** <objective yes/no test>
- **If it fails:** <troubleshooting guidance or "stop, file a bug">
```

## Suggested additions

When you have time, add test cases for:

- Specific RF parameters at boundary conditions (TX EVM at -45 / 0 / +28 dBm)
- DMM measurement accuracy against a known calibration source
- SA dynamic range (verify SA can measure both -100 dBm and +20 dBm signals)
- WFG bandwidth / sample-rate sweep
- DB schema integrity after a large number of sessions (1000+)
- Dashboard load with 100+ sessions

Submit additions as PRs to this document.

---

# Sign-off page

| Phase | Status | Engineer | Date |
|---|---|---|---|
| Phase 0 — Lab machine setup | ☐ | ___ | ___ |
| Phase 1 — V1c CMW100 + DUT | ☐ | ___ | ___ |
| Phase 2 — V1d/V1e migrator | ☐ | ___ | ___ |
| Phase 3 — V1f DMM | ☐ | ___ | ___ |
| Phase 4 — V2 HTML + bulk migration | ☐ | ___ | ___ |
| Phase 5 — V3 SG / SA / WFG | ☐ | ___ | ___ |
| Phase 6 — V4 persistent results | ☐ | ___ | ___ |
| Phase 7 — V5 lab orchestration | ☐ | ___ | ___ |
| Phase 8 — End-to-end integration | ☐ | ___ | ___ |
| **v1.0.0 sign-off** | ☐ | ___ | ___ |

When all phases are signed off, file an issue titled "v1.0.0 bench validation complete" and attach:
- The completed sign-off page (this file with checkboxes ticked)
- `reports/integration.html` from Phase 8
- The 5 instruments' `*IDN?` strings from the equipment checklist

That's the trigger to tag **v1.0.0 (final)**.
