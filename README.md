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
5. **Migration CLI:** `openflow migrate <old_test.py>` rewrites an OpenTAP-Python test into a bare-metal pytest test using libcst. 22 transformer stages (11 V1a + 5 V1c + 1 V1d + 3 V1e + 2 V2).
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

| Phase | Scope | Spec | Plan | Status |
|---|---|---|---|---|
| **v1** | Framework + AST migrator + Tx EVM Power Sweep ported + real CMW100/DMM/DUT_U300/FT2232H drivers | [v1 design](./docs/superpowers/specs/2026-05-22-openflow-v1-design.md) | [v1a plan](./docs/superpowers/plans/2026-05-22-openflow-v1a.md) | ✅ Shipped (v0.4.0) — V1a + V1b + V1c + V1d + V1e + V1f |
| **v2** | Bulk migration of the remaining U300 EVT suite + HTML report renderer + 2 more migrator transformers | [v2 design](./docs/superpowers/specs/2026-05-22-openflow-v2-design.md) | [v2 plan](./docs/superpowers/plans/2026-05-22-openflow-v2.md) | 📋 Planned — engineer-input needed for source files |
| **v3** | Real driver ports for SG / SA / WFG (DMM already shipped in V1f) | [v3 design](./docs/superpowers/specs/2026-05-22-openflow-v3-design.md) | [v3 plan](./docs/superpowers/plans/2026-05-22-openflow-v3.md) | 📋 Planned |
| **v4** | Persistent results — SQLite default, optional PostgreSQL; trend-analysis CLI | [v4 design](./docs/superpowers/specs/2026-05-22-openflow-v4-design.md) | [v4 plan](./docs/superpowers/plans/2026-05-22-openflow-v4.md) | 📋 Planned (gated on V3 bench feedback) |
| **v5** | Lab orchestration — bench reservation, multi-DUT parallel runs, read-only web dashboard | [v5 design](./docs/superpowers/specs/2026-05-22-openflow-v5-design.md) | [v5 plan](./docs/superpowers/plans/2026-05-22-openflow-v5.md) | 📋 Planned (gated on V4 + team scale) |

## History

- **v0.1.0** (archived): an earlier C#/.NET thin runner on top of OpenTAP. Preserved at
  tag [`v0.1.0-csharp-archived`](https://github.com/mayhuifu/OpenFlow/releases/tag/v0.1.0-csharp-archived)
  and branch [`archive/csharp-runner`](https://github.com/mayhuifu/OpenFlow/tree/archive/csharp-runner).
  Replaced by this Python pivot after engineering review concluded that OpenTAP
  itself — not the runner around it — was the source of test-author friction.

## License

[MIT](./LICENSE) © 2026 Huifu Ma.
