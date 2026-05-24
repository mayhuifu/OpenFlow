# Bench bring-up tests

Smoke and diagnostic tests for bringing up a fresh CMW100 + U300 bench with
OpenFlow. Run these **in order** when setting up a new lab machine or after
swapping hardware. Each is small (<50 lines) and isolates one component so
failures point at one cause.

## Order

| # | File | What it checks | Required for next |
|---|---|---|---|
| 1 | `test_01_cmw100_connectivity.py` | LAN → CMW100 → R&S SDK → `*IDN?` round-trip. No NR config touched. | Foundation — must pass before anything else. |
| 2 | `test_02_cmw100_nr_diagnostics.py` | Dumps `*OPT?`, `INSTrument:LIST?`, `INSTrument:SELect?`, NRSub probe. Always passes (no asserts). | Run if test 03 fails with SCPI errors. |
| 3 | `test_03_cmw100_tx_evm_smoke.py` | 5-point TX-EVM sweep via NR FR1 Meas SDK. No DUT, no calibration data. | Proves the full CMW100 measurement chain works. |
| 3b | `test_03b_cmw100_lte_tx_evm_smoke.py` | **Alternate to test_03 for LTE-only CMW100s** (KM500 license, no NR). 5-point LTE TX-EVM sweep. v1.0.0-rc2. | Proves LTE measurement chain works on benches without NR FR1 Meas options. |
| 3c | `test_03c_cmw100_lte_diagnostics.py` | **Diagnostic for LTE -114 errors.** Probes INSTrument:CREate/SELect, multiple SCPI forms, and RsCmwLteMeas SDK paths. Always passes (no asserts). v1.0.0-rc5. | Run if test_03b fails with `-114 "Header suffix out of range"`. SUMMARY block tells you which fix the framework needs. |
| 3d | `test_03d_cmw100_lte_diagnostics_v2.py` | **Deeper LTE diagnostic.** Probes INSTrument:SELect unquoted keywords + INSTrument:NSELect 1..6 sweep + GPRF measurement tree + LTE:SIGNaling tree + exhaustive SDK attribute dump. v1.0.0-rc6. | Run if 03c showed `-113` on `INSTrument:CREate` (no multi-app architecture). Plus: **manually verify the CMW100 front panel shows an active LTE Meas application before running.** |
| 4 | `test_04_dmm_connectivity.py` | LAN → Keysight 34461A DMM → pyvisa → `*IDN?` round-trip. (V1f driver, V3 bring-up.) | Independent of CMW100; required before any test that reads currents. |
| 5 | `test_05_sg_connectivity.py` | LAN → R&S SMW200A SG → pyvisa → `*IDN?` round-trip. (V3.) | Independent; required before RX sensitivity tests. |
| 6 | `test_06_sa_connectivity.py` | LAN → Keysight N9020B MXA (or R&S FSW) → pyvisa → `*IDN?` round-trip. (V3.) | Independent; required before RX measurement tests. |
| 7 | `test_07_wfg_connectivity.py` | LAN → Keysight 33500B WFG → pyvisa → `*IDN?` round-trip. (V3.) | Independent; required before any test that drives BB signals via WFG. |

Tests 1-3 cover the CMW100 chain; tests 4-7 cover each individual bench
instrument the migrated EVT suite uses. They can be run in any order
since they're independent of each other.

## Running

### Pick the right config for your test

As of v1.0.0-rc10 there are three configs in `tests/configs/`:

| Config | Tuned for | Use with |
|---|---|---|
| `u300b0_evt.yaml` | Legacy default (NR n78 numbers, `MOCK::` resources) | Demo / migration tests in CI |
| `u300b0_evt_nr.yaml` | **5G NR n78** — 3.5 GHz, 100 MHz BW, 16QAM | `test_03_cmw100_tx_evm_smoke.py` (NR sweep) |
| `u300b0_evt_lte.yaml` | **LTE FDD B7** — 2.65 GHz, 10 MHz BW, QPSK | `test_03b_cmw100_lte_tx_evm_smoke.py` (LTE sweep) |

Both `_nr.yaml` and `_lte.yaml` ship with the SZLABPC-WIN04 VXI-11 resource
(`TCPIP::10.61.8.135::inst0::INSTR`) — edit those two lines for your bench.

### Run them in order

From the repo root:

```sh
# Connectivity + diagnostics — either config works (they only touch *IDN?)
uv run pytest tests/bench_bringup/test_01_cmw100_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt_nr.yaml \
    --openflow-report=reports/01-conn.json --log-cli-level=INFO -v

uv run pytest tests/bench_bringup/test_02_cmw100_nr_diagnostics.py \
    --openflow-config=tests/configs/u300b0_evt_nr.yaml \
    --openflow-report=reports/02-diag.json --log-cli-level=INFO -v

# NR TX-EVM smoke — uses the NR config (n78, 3.5 GHz, 100 MHz)
uv run pytest tests/bench_bringup/test_03_cmw100_tx_evm_smoke.py \
    --openflow-config=tests/configs/u300b0_evt_nr.yaml \
    --openflow-report=reports/03-nr-smoke.json --log-cli-level=INFO -v

# LTE TX-EVM smoke — uses the LTE config (B7, 2.65 GHz, 10 MHz)
uv run pytest tests/bench_bringup/test_03b_cmw100_lte_tx_evm_smoke.py \
    --openflow-config=tests/configs/u300b0_evt_lte.yaml \
    --openflow-report=reports/03b-lte-smoke.json --log-cli-level=INFO -v
```

PowerShell users: use backtick (\` \`) for line continuation, **not** backslash.
Backslash will cause `pytest` to treat the next line as a separate command and
the `--openflow-config` flag won't reach the test runner.

Or all at once (each writes its own report file):

```sh
uv run pytest tests/bench_bringup/ \
    --openflow-config=tests/configs/u300b0_evt_nr.yaml \
    --log-cli-level=INFO -v
```

Note: these tests need a **real CMW100 reachable over VISA**. They are NOT
part of the CI suite — CI runs `tests-internal/` only.

## Reading the YAML

`tests/configs/u300b0_evt.yaml` defines:
- `instruments.cmw100.resource` — the VISA address of your CMW100
- `band`, `modulation`, `rfbw_Hz`, `dl_freq_pll_Hz`, `ul_freq_pll_Hz`, etc. — RF parameters
- `dut.type` — `stub` (V1a default), `u300`, or `ft2232h`. The bring-up tests
  don't request the `dut` fixture so this is mostly irrelevant for them.

Edit that file before your first run to point at your bench's CMW100.

## If test 01 fails

| Symptom | Likely cause | Fix |
|---|---|---|
| `pyvisa.errors.VisaIOError: Could not connect` | Wrong resource string, CMW100 powered off, firewall | Check `ping <ip>`, verify the resource in YAML, confirm CMW100 LAN settings |
| `ModuleNotFoundError: No module named 'rscmw_base'` | `uv sync` didn't complete | Re-run `uv sync`; if PyPI unreachable, use the offline bundle |
| `pending_errors` non-empty | CMW100 has stale errors from a previous session | Send `*CLS` manually via the CMW100 front panel, or run the test twice |

## If test 03 fails with "Header suffix out of range"

That's a CMW100-side error meaning the NR FR1 Meas measurement instance
doesn't exist yet. Run test 02 to see whether:
- The NR FR1 Meas software option is licensed (`*OPT?` shows an "NR" entry)
- The application has been instantiated (`INSTrument:SELect?` returns
  something NR-related)

If both look correct and you still get the error, the fix is likely to add
an `INSTrument:CREate "NR Sub Meas Q4"` (or equivalent) call to
`CMW100.open()` in `openflow/instruments/cmw100.py`. The exact app name
depends on what test 02 shows in `INSTrument:LIST?`.
