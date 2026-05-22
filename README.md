# OpenFlow

Bare-metal Python test framework for RF / baseband hardware test automation.

OpenFlow replaces the OpenTAP-based test harness with a thin pytest plugin: tests
are normal Python files, sweeps come from `@pytest.mark.parametrize`, verdicts
come from `assert`, instruments arrive as fixtures, and config lives in YAML —
nothing else.

## Status

🚧 **Pre-implementation.** v1 design is drafted and awaiting engineering review.
See [docs/superpowers/specs/2026-05-22-openflow-v1-design.md](docs/superpowers/specs/2026-05-22-openflow-v1-design.md).

## What v1 ships

1. A pytest plugin (`openflow.plugin`) with fixtures: `cmw100`, `dut`, `config`, `results`.
2. A YAML config loader with typed validation.
3. A CMW100 driver (SCPI over LAN via PyVISA) covering the methods used by the
   Tx EVM Power Sweep test.
4. A migration CLI: `openflow migrate <old_test.py>` rewrites an OpenTAP-Python
   test into a bare-metal pytest test using libcst.
5. The `U300B0_RFEB_EVT_TX_EVM_Power_Sweep` test ported, running against a real
   CMW100, producing a JSON report.

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
uv run pytest tests/test_rx_gain_accuracy.py --config tests/configs/u300b0_evt.yaml --report report.json
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
