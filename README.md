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
5. **Migration CLI:** `openflow migrate <old_test.py>` rewrites an OpenTAP-Python test into a bare-metal pytest test using libcst. 11 transformer stages.
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

## Quickstart (V1a)

```sh
# Set up
uv sync

# Run the internal test suite (framework + migrator, no bench needed)
uv run pytest tests-internal

# Convert an OpenTAP-Python test to bare-metal pytest
uv run openflow migrate path/to/OpenTAP_Test.py
# → emits path/to/test_opentap_test.py + summary of items to clean up

# Collect-check the V1a migrated demo (no bench needed)
uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py \
  --openflow-config=tests/configs/u300b0_evt.yaml --collect-only

# Bench run (V1b — needs real CMW100 + DUT_U300 once V1b lands)
uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py \
  --openflow-config=tests/configs/u300b0_evt.yaml \
  --openflow-report=report.json
```

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
