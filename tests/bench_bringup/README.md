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

V2 will add `test_04_dut_*` (DUT_U300 SPI / register-map smoke once the
source-level stubs in `openflow/dut/u300.py` are resolved) and `test_05_dmm_*`
(once a real DMM driver replaces the V1a stub).

## Running

From the repo root:

```sh
# Run them in order:
uv run pytest tests/bench_bringup/test_01_cmw100_connectivity.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=01-conn.json --log-cli-level=INFO -v

uv run pytest tests/bench_bringup/test_02_cmw100_nr_diagnostics.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=02-diag.json --log-cli-level=INFO -v

uv run pytest tests/bench_bringup/test_03_cmw100_tx_evm_smoke.py \
    --openflow-config=tests/configs/u300b0_evt.yaml \
    --openflow-report=03-smoke.json --log-cli-level=INFO -v
```

Or all at once (each writes its own report file):

```sh
uv run pytest tests/bench_bringup/ \
    --openflow-config=tests/configs/u300b0_evt.yaml \
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
