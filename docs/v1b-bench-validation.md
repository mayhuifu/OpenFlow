# V1b Bench Validation Guide

V1b's "ship" criterion is that the bench engineer can run
`tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py` against a real CMW100 + a
real U300 RFIC on the FTDI2232H bridge and get plausible verdicts.

This file walks through the manual cleanup that connects V1b's mechanical ports
to a working bench run.

## Bench machine setup (first time)

### 1. Install `uv` (one-time per machine)

OpenFlow uses [`uv`](https://docs.astral.sh/uv/) to manage Python + dependencies
deterministically from `pyproject.toml` + `uv.lock`.

**macOS / Linux:**
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Confirm with `uv --version` (expect `uv 0.4+` or newer).

### 2. Get the repo

If the lab machine **has GitHub access**:
```sh
git clone https://github.com/mayhuifu/OpenFlow.git
cd OpenFlow
```

If the lab machine **does NOT have GitHub access**, the developer ships a zip:
```sh
# Developer (on machine with GitHub access):
scripts/make-offline-bundle.sh             # source-only bundle (~250 KB)
# or:
scripts/make-offline-bundle.sh --offline   # source + wheels (~700-900 MB, airgapped)

# scp dist/OpenFlow-*.zip to lab machine, then on the lab machine:
unzip OpenFlow-YYYYMMDD-HHMMSS-*.zip
cd OpenFlow
```

Everything below runs from the repo root (the directory containing
`pyproject.toml`).

### 3. Sync dependencies

```sh
# If the developer sent the source-only bundle (or you git-cloned):
uv sync
# This reads pyproject.toml + uv.lock and creates a .venv/ directory with
# all pinned dependencies. First run downloads ~700 MB.

# If the developer sent the OFFLINE bundle (wheels/ folder present):
uv sync --offline --find-links wheels/
# Reads wheels/requirements.txt + the bundled wheels — no PyPI hit.
```

**You do NOT need to activate `.venv/` manually.** Always invoke commands
through `uv run <command>` — uv finds the project venv automatically.

### 4. OS-specific notes for native dependencies

- **`pyftdi`** (USB SPI control for the FTDI2232H bridge):
  - **macOS:** works out of the box; libusb is in the SDK.
  - **Linux:** install `libusb-1.0-0` via your package manager
    (`sudo apt install libusb-1.0-0` on Debian/Ubuntu). May also need
    `udev` rules for the FTDI device:
    ```sh
    # /etc/udev/rules.d/11-ftdi.rules
    SUBSYSTEM=="usb", ATTRS{idVendor}=="0403", ATTRS{idProduct}=="6010", MODE="0666"
    ```
    Then `sudo udevadm control --reload-rules && sudo udevadm trigger`.
  - **Windows:** install the FTDI WinUSB driver via
    [Zadig](https://zadig.akeo.ie/) (replaces the default VCP driver
    for the FT2232H bulk endpoints). pyftdi docs explain.
- **R&S Python SDK** (`rscmw-base`, `RsCmwGprfGen/Meas`, `RsCmwLte*`,
  `RsCmwNrFr1Meas`): pure-Python wheels — install via `uv sync` succeeds on
  any OS without extra setup. They open VISA sessions via the CMW100's own
  TCP/IP socket interface; no separate VISA backend (NI-VISA / Keysight IO)
  is required.
- **`numpy` + `pandas`:** prebuilt wheels for all major OSes; no compilation.

### 5. Confirm setup is good

```sh
uv run pytest tests-internal
```

**Expected:** `154 passed` (give or take a few as V1b/V2 work continues),
~1 second runtime. If anything errors, the imports and dependency wiring are
the most likely culprits — share the output with the team.

Optionally also verify the migrated demo file is parseable:
```sh
uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py \
  --openflow-config=tests/configs/u300b0_evt.yaml --collect-only
```
**Expected:** `1 test collected`.

### 6. Running the migration CLI

After `uv sync` the `openflow` CLI is available via `uv run`:

```sh
uv run openflow migrate /path/to/some_OpenTAP_test.py --out tests/test_some_new.py
```

(The `--out` defaults to alongside the source with a `test_` prefix if you
omit it.)

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `uv: command not found` | uv not on PATH after install | Restart shell, or add `~/.local/bin` (Linux/macOS) / `%USERPROFILE%\.local\bin` (Windows) to PATH |
| `uv sync` fails with `No matching distribution` for an `RsCmw*` package | Behind a corporate proxy that blocks pypi.org | Configure pip/uv proxy: `uv sync --index-url https://<your-mirror>/simple` or set `HTTPS_PROXY` |
| `pyftdi.usbtools.UsbToolsError: Could not find any FTDI` on Linux | udev rules missing or user not in `plugdev` group | Apply the udev rules in step 4 + `sudo usermod -aG plugdev $USER` + log out/in |
| `pytest` shows `ModuleNotFoundError: No module named 'openflow'` | Ran `pytest` directly instead of `uv run pytest` | Always prefix with `uv run` (or activate `.venv` manually if you prefer) |
| Plugin discovery error: `openflow.plugin` module not loadable | Editable install out of date (rare) | `uv sync --reinstall` |

---

## Status of the pieces

| Component | V1b status | What's needed for a real bench run |
|---|---|---|
| `openflow.instruments.cmw100` (CMW100 façade + mixins) | Ported; emulation mode works in CI | Set `instruments.cmw100.resource` in YAML to a real TCPIP/USB VISA string. R&S Python SDK calls drive the bench. |
| `openflow.dut.ft2232h` (DUT_FT2232h_V03) | Ported faithfully | `pyftdi` already a dep. Connect FTDI dongle. Set `dut.emulation: false`, `dut.ftdi_address: "ftdi://ftdi:2232h:<serial>"`, `dut.reg_map_file: "U300_RFIC_A0_V00.csv"`. |
| `openflow.dut.u300` (DUT_U300) | Partial port — see below | Several methods in the original source are themselves stubs. Real bench operation requires completing those source-level stubs OR wiring up `rfd_simulator`. |
| `openflow.rfengine.{deembedding,testconditions_limits,calibration_file}` | Ported | Provide real YAML/CSV files at the paths your `limits_path`, `deembedding_path`, `calibration_path` point at. |
| Migrated demo `tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py` | Generated by the migrator (V1a). Collects cleanly, does not run end-to-end. | Manual cleanup steps below. |

## Source-level stubs in `DUT_U300` (warn before bench)

When V1b ported DUT_U300, several methods turned out to be stubs in the
**original UMT source**:
- `cmd_initialize` — original body relied on `rfd_simulator` register-map imports (OpenTAP-specific emulation helper).
- `set_rfTxStop`, `set_arb_signal_bb`, `set_arb_power_dBFSrms`, `set_rfTxPower` (real-hardware path beyond emulation return), `load_reg_map`, `save_reg_map` — original source body was `pass` or `log.Error("Function not implemented")`.

V1b's port preserves the stub behavior faithfully (CI passes in emulation; real
hardware would log warnings and silently no-op). **Before bench validation**,
the engineer must:

1. Either complete the source-level implementations and re-port them, or
2. Vendor `rfd_simulator` separately and re-add its hooks in `openflow.dut.u300`, or
3. Accept that the demo will exercise the framework + CMW100 + emulation DUT
   only — not a true end-to-end RF measurement.

## Manual cleanup of the migrated test file

**V1c update (2026-05-22):** the migrator now handles steps 1, 2, 3, 5, and 8
automatically. What used to be an 8-step manual checklist is now 3 remaining
steps (4, 6, 7) — all genuine RF engineering judgment.

**V1d update (2026-05-22):** step 2 is now fully complete — the migrator
not only strips `self.in_` prefixes but also renames the three legacy
`*_config` file-path inputs to their `*_path` OpenFlowConfig field names.

**V1e update (2026-05-22):** step 4 is now mostly automated — the migrator
auto-renames `Setup_DMM`/`Get_DMM`/`Get_Aux` to their lowercase forms
and injects the `from openflow.rfengine.evt_base import ...` line. A new
step (auto-emitting a `CLASS_NAME` constant so `self.__class__.__name__`
becomes runtime-safe) was added as item 9.

Original 8 steps + V1e item 9, with current status:

| # | Step | Status |
|---|---|---|
| 1 | Add `import logging` + logger | ✅ Automated by `AddLoggingHeader` transformer (V1c) |
| 2 | Replace `self.in_*` → `config.*` (incl. `_config` → `_path` renames) | ✅ Automated by `RewriteInputAttrs` (V1c) + `RewriteConfigNames` (V1d) transformers |
| 3 | Replace `self.out_*` + `PublishResult()` → locals + `results.publish(**)` | ✅ Automated by `RewriteOutputPublish` transformer (V1c, recurses into nested for/if/try blocks) |
| 4 | Replace inherited helpers (`Setup_DMM`, `Get_DMM`, `Get_Aux`) | ✅ Automated by `RewriteEvtHelperCalls` transformer (V1e). Calls are renamed + the `from openflow.rfengine.evt_base import ...` line is auto-injected. **Note:** the emitted call uses a placeholder `dmms={}` — the engineer fills in their bench's DMM dict. `Print_Summary` is intentionally NOT auto-rewritten (V2 candidate). |
| 5 | Replace `RFEB_SN`/`RFHB_SN` | ✅ Automated by `RewriteBoardSerials` transformer + `OpenFlowConfig.rfeb_sn`/`rfhb_sn` fields (V1c-6) |
| 6 | Convert sweep loops to `@pytest.mark.parametrize` | ❌ **Manual.** Judgment call — only works cleanly for simple outer loops without per-iteration setup. |
| 7 | Handle nested verdict logic (MPR-skip vs fail) | ❌ **Manual.** Pure RF engineering judgment; migrator can't infer test intent. |
| 8 | Strip bare `except:` blocks | ✅ Automated by `StripBareExcept` transformer (V1c) |
| 9 | Replace `self.__class__.__name__` with `CLASS_NAME` constant | ✅ Automated by `CaptureClassName` + `RewriteClassDunderName` transformers (V1e) |

### Step 2 in detail — config field renames (V1d)

`RewriteInputAttrs` strips the `in_` prefix from input-property reads, but
three of the OpenTAP input names ended in `_config` while OpenFlowConfig
calls the same fields `*_path`. `RewriteConfigNames` closes that gap:

| OpenTAP-Python name (post-`in_`-strip) | OpenFlowConfig field |
|---|---|
| `config.conditions_limits_config` | `config.limits_path` |
| `config.deembedding_config` | `config.deembedding_path` |
| `config.calibration_file_config` | `config.calibration_path` |

Mapping table lives in `openflow/migrate/transformers.py` near
`_CONFIG_NAME_MAP`. Add a new entry there if you migrate a test that
uses an OpenTAP input whose name doesn't match its OpenFlowConfig field.

### Step 4 in detail — porting EVT base helpers

`openflow.rfengine.evt_base` exposes:

```python
from openflow.rfengine.evt_base import setup_dmm, get_dmm, get_aux

# In the test:
setup_dmm(dmms={"dmm_c": dmm_c, "dmm_ibat": dmm_ibat, ...})  # configures each to current mode
readings = get_dmm(dmms={"dmm_c": dmm_c, "dmm_ibat": dmm_ibat, ...})  # returns dict of out_* keys
aux_readings = get_aux(dut)  # returns dict of dut auxiliary measurements
```

The migrated test currently has bare `Setup_DMM()` / `Get_DMM()` / `Get_Aux()` calls. Replace each with the imported function. The DMM dict shape matches the OpenTAP source (8 DMMs: `dmm_c`, `dmm_idd1v4`, `dmm_idd1v8`, `dmm_idd2v5`, `dmm_iapt`, `dmm_ibat`, `dmm_ifem1v2`, `dmm_ifem1v8`); pass only the ones your bench has wired up (missing entries are skipped).

### Step 6 in detail — Convert the sweep loops into `@pytest.mark.parametrize`

The original Run() body had `for modulation in ["16QAM"]:` and
`for target_tx_power in np.arange(-45, 28+1, 1.0):`. The cleanest pytest
pattern is to lift these into parametrize decorators:

```python
@pytest.mark.testcase(TESTCASE_ID)
@pytest.mark.parametrize("modulation", ["16QAM"])
@pytest.mark.parametrize("target_tx_power", list(np.arange(-45, 29, 1.0)))
def test_u300b0_rfeb_evt_tx_evm_power_sweep(
        cmw100, wfg, dut, dmm_c, dmm_v, config, results,
        modulation, target_tx_power):
    ...
```

Each iteration is now a separate test case in the report.

### Step 7 in detail — Handle the nested verdict logic

The original test has:
```python
if self.out_EVM_pct <= (target_evm_max - target_evm_margin):
    self.UpgradeVerdict(OpenTap.Verdict.Pass)
else:
    if self.out_tx_power_dBm <= (txpowermax - txmpr):
        self.UpgradeVerdict(OpenTap.Verdict.Fail)
    else:
        self.log.Debug(f'Tx Output Power Max exceeded for this signal')
```

The migrator translated this to `pass` / `assert False`. For correctness on
real hardware, use `pytest.skip(...)` for the "MPR exceeded — don't measure"
branch:

```python
if out_EVM_pct <= (target_evm_max - target_evm_margin):
    pass  # passing the EVM limit
else:
    if out_tx_power_dBm <= (txpowermax - txmpr):
        assert False, f"EVM {out_EVM_pct}% exceeds limit {target_evm_max}%"
    else:
        pytest.skip(f"Tx output power exceeds max with MPR — skipping verdict")
```

### Step 8 — Strip bare `except:` blocks

✅ Automated by V1c — bare `except:` is rewritten to `except Exception:`.
For tighter exception handling, the engineer may still want to specialize
(e.g. `except pyvisa.errors.VisaIOError`).

## Bench-run command (after manual cleanup)

```sh
# Connect: CMW100 reachable at TCPIP; U300 board reset; FTDI dongle plugged in
uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py \
  --openflow-config=tests/configs/u300b0_evt.yaml \
  --openflow-report=report.json \
  --log-cli-level=INFO -v
```

Expected: 74 parametrized iterations (one per power level in the sweep), each
producing a record in `report.json` with measured `out_tx_power_dBm` and
`out_EVM_pct`. Verdicts compare against limits loaded from
`configs/limits/U300B0.yaml`.

## When V1b is "done"

- [ ] Manual cleanup steps 1–8 applied to the migrated test file.
- [ ] `tests/configs/u300b0_evt.yaml` updated with `dut.type: u300`,
      `dut.emulation: false`, `ftdi_address`, `reg_map_file`, real CMW100
      VISA resource.
- [ ] Real `configs/limits/U300B0.yaml`, `configs/deembedding/U300B0.yaml`,
      `configs/calibration/U300B0.yaml` provided.
- [ ] Source-level stubs in `openflow.dut.u300` resolved (either by completing
      the source implementations + re-porting, or by accepting framework-only
      validation).
- [ ] One full sweep completes without crashing on a real bench.
- [ ] Engineer signs off on a sample `report.json` matching expectations.

## What V1c shipped (resolving steps 1, 2, 3, 5, 8 + helper port for step 4)

All of these were originally listed as "V2 work" but landed in V1c:

- ✅ `AddLoggingHeader` transformer (step 1)
- ✅ `RewriteInputAttrs` transformer (step 2)
- ✅ `RewriteOutputPublish` transformer with nested-block recursion (step 3)
- ✅ Port of `U300_RFEngine_EVT_Base` helpers to `openflow.rfengine.evt_base` (step 4 — engineer still does the rename + import)
- ✅ `RewriteBoardSerials` transformer + config fields (step 5)
- ✅ `StripBareExcept` transformer (step 8)

## What V2 will still smooth out

- A transformer that rewrites `Setup_DMM()` → `setup_dmm(dmms=…)` calls to
  fully automate step 4.
- A transformer that lifts simple loop bodies into `@pytest.mark.parametrize` (step 6).
- A transformer that adds `pytest.skip(...)` for known "should not have been measured" branches (step 7 — at least the common patterns).
