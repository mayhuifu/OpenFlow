# OpenFlow

Bare-metal Python test framework for RF / baseband hardware test automation.

OpenFlow replaces the OpenTAP-based test harness with a thin pytest plugin: tests
are normal Python files, sweeps come from `@pytest.mark.parametrize`, verdicts
come from `assert`, instruments arrive as fixtures, and config lives in YAML —
nothing else.

## Status

🚀 **V1a shipped on the `python-v1` branch.** Framework + migration tool + one
migrated demo test, all green in CI under emulation. Bench validation (V1b)
remains, gated on porting `DUT_U300` + `DUT_FT2232H` from the existing
`UMT_DUTs` package.

- Spec: [`docs/superpowers/specs/2026-05-22-openflow-v1-design.md`](docs/superpowers/specs/2026-05-22-openflow-v1-design.md)
- Plan: [`docs/superpowers/plans/2026-05-22-openflow-v1a.md`](docs/superpowers/plans/2026-05-22-openflow-v1a.md) (+ [supplement](docs/superpowers/plans/2026-05-22-openflow-v1a-supplement.md))

## What V1a ships

1. **Pytest plugin** (`openflow.plugin`) with fixtures: `cmw100`, `dut`, `config`, `results`, plus stub fixtures `wfg`, `dmm_c`, `dmm_v` for the migrated test's signature.
2. **YAML config loader** with pydantic v2 typed validation (`openflow.config`).
3. **CMW100 driver** (`openflow.instruments.cmw100`) — port of `UMT_Instruments/CMW100.py` minus OpenTAP, using R&S's official Python SDK (`RsCmwGprfGen`, `RsCmwGprfMeas`, `RsCmwNrFr1Meas`, etc.). The TX-EVM subset of measurements is ported (`setup_NrTx`, `meas_NrTxAll`, `meas_NrTxEVM`, `meas_NrTxPower`); other measurements port on demand.
4. **rfengine helpers** (`openflow.rfengine.{deembedding,testconditions_limits,calibration_file}`) — ports of the three loaders from `U300_RFEngine/`.
5. **Migration CLI:** `openflow migrate <old_test.py>` rewrites an OpenTAP-Python test into a bare-metal pytest test using libcst. 17 transformer stages (11 in V1a + 5 in V1c + 1 in V1d).
6. **Migrated demo:** `tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py` (output of the migrator on the real TX EVM source), collects cleanly via `pytest --collect-only`.

## Quick taste

A migrated test:

```python
import pytest

TESTCASE_ID = "U300B0-RFE-EVT-002"
RX_GAIN_TABLE = [61, 58, 55, 52, 49, 46, 43, 40, 37, 34, 30, 27, 24, 21, 18, 15, 12, 9, 6, 3, 0]

@pytest.mark.testcase(TESTCASE_ID)
@pytest.mark.parametrize("gain", RX_GAIN_TABLE)
def test_rx_gain_accuracy(dut, vsa, sg, config, results, gain):
    target = config.limit("GAIN_DELTA", band=config.band, bandwidth_hz=config.rfbw_hz)
    deemb  = config.deembedding(top="RX", uldl=config.dl_config_active, band=config.band, freq=config.dl_freq_pll_hz)

    dut.cmd_initialize()
    dut.set_rfAssignDlCarriers(...)
    predicted = dut.set_rfRxGain(gain)[config.rx_idx]

    sg.set_arb_signal_rf(..., power_level=-predicted - config.rx_power_backoff_dB - deemb.rfeb - deemb.ant)
    dut.setup_NRRx(sa=vsa, ...)
    rx_gain_delta = (dut.meas_NrRxPower(sa=vsa, ...) - deemb.bb) - predicted

    results.publish(gain_setting=gain, rx_gain_delta=rx_gain_delta)
    assert abs(rx_gain_delta) <= target, f"Gain error {rx_gain_delta:.2f} dB exceeds {target} dB"
```

Run it:

```sh
uv sync
uv run pytest tests/test_rx_gain_accuracy.py \
  --openflow-config=tests/configs/u300b0_evt.yaml \
  --openflow-report=report.json
```

## Quickstart

```sh
# Set up
uv sync

# 1. Confirm framework health (no bench needed):
uv run pytest tests-internal
# → 201 tests pass

# 2. New bench? Start with the bring-up sequence:
uv run pytest tests/bench_bringup/test_01_cmw100_connectivity.py \
  --openflow-config=tests/configs/u300b0_evt.yaml \
  --openflow-report=01-conn.json --log-cli-level=INFO -v

# See tests/bench_bringup/README.md for the full bring-up walkthrough.

# 3. Convert an OpenTAP-Python test to bare-metal pytest:
uv run openflow migrate path/to/OpenTAP_Test.py
# → emits path/to/test_opentap_test.py + summary of items to clean up

# 4. Full demo test (still needs engineer-provided limits/deembedding/calibration data):
uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py \
  --openflow-config=tests/configs/u300b0_evt.yaml \
  --openflow-report=report.json
```

## Bench bring-up (recommended starting point on new hardware)

Three smoke tests in [`tests/bench_bringup/`](./tests/bench_bringup/) isolate
each component so failures point at one cause:

| # | Test | What it proves |
|---|---|---|
| 1 | `test_01_cmw100_connectivity.py` | LAN + SDK + VISA path is healthy |
| 2 | `test_02_cmw100_nr_diagnostics.py` | NR FR1 Meas license + app state (diagnostic-only) |
| 3 | `test_03_cmw100_tx_evm_smoke.py` | Full CMW100 NR measurement chain (5-point sweep) |

See [`tests/bench_bringup/README.md`](./tests/bench_bringup/README.md) for the
recommended order and troubleshooting tips.

## Transferring the repo to a lab machine without GitHub

```sh
scripts/make-offline-bundle.sh             # ~250 KB source-only zip
scripts/make-offline-bundle.sh --offline   # ~700-900 MB source + pinned wheels
```

Output lands in `dist/`. Engineer unzips on the bench machine, runs `uv sync`,
then continues with the bring-up sequence above.

## Roadmap

1. **v1** — Framework + AST migrator + Tx EVM Power Sweep ported and running against CMW100.
2. **v2** — Bulk migration of the U300 EVT suite using the v1 converter; HTML report renderer.
3. **v3** — Full instrument coverage (SG, SA, WFG, DMM); update migrator for any new patterns.
4. **v4** — Persistent results (SQLite, optional PostgreSQL); enables trend analysis.
5. **v5** — Lab orchestration: bench reservation, multi-DUT parallel runs, read-only web dashboard.

## History

- **v0.1.0** (archived): an earlier C#/.NET thin runner on top of OpenTAP. Preserved at
  tag [`v0.1.0-csharp-archived`](https://github.com/mayhuifu/OpenFlow/releases/tag/v0.1.0-csharp-archived)
  and branch [`archive/csharp-runner`](https://github.com/mayhuifu/OpenFlow/tree/archive/csharp-runner).
  Replaced by this Python pivot after engineering review concluded that OpenTAP
  itself — not the runner around it — was the source of test-author friction.

## License

[MIT](./LICENSE) © 2026 Huifu Ma.
