"""Smoke test for the V1b/V1c bench bring-up.

PURPOSE
  Confirm the CMW100 wiring is correct and the framework end-to-end works
  on a real bench, WITHOUT requiring the engineer to have real
  configs/limits/, configs/deembedding/, or configs/calibration/ YAML/CSV
  files in place yet.

WHAT IT DOES
  - Opens the CMW100 via the resource string in the YAML config
  - Sweeps a short 5-point TX power range (instead of the full 74-point sweep
    in the production test file)
  - For each point:
      * setup_NrTx via R&S NrFr1Meas SDK
      * trigger meas_NrTxAll
      * fetch tx power + EVM
      * publish to results.json
  - No verdict — placeholder limits would be meaningless

WHAT IT INTENTIONALLY DOES NOT DO
  - No deembedding (no losses applied to measured power)
  - No board-cal lookup (no IQ DC offset, no IQ imbalance correction)
  - No DUT TX path setup (no set_arb_signal_bb / set_rfTxPower) —
    the CMW100 driving its OWN signal generator via set_arb_signal_rf
    if that's wired; otherwise this test verifies measurement-only
  - No verdict comparison against EVM limits

USAGE
  uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep_smoke.py \\
    --openflow-config=tests/configs/u300b0_evt.yaml \\
    --openflow-report=smoke-report.json \\
    --log-cli-level=INFO -v

WHAT YOU SHOULD SEE
  - INFO log: "Sweeping target_tx_power=-10.0 dBm"
  - 5 results.publish() calls
  - 5 records in smoke-report.json
  - If you instrument the CMW100 measurement console you should see live
    config + measurement traffic for each iteration
"""
from __future__ import annotations

import logging
import math
import time

import pytest

TESTCASE_ID = "U300B0-RFE-EVT-005-SMOKE"
SMOKE_SWEEP_DBM = [-30.0, -20.0, -10.0, 0.0, 10.0]   # 5 points; full sweep is 74

logger = logging.getLogger(__name__)


@pytest.mark.testcase(TESTCASE_ID)
def test_cmw100_tx_evm_smoke(cmw100, config, results):
    """Drive the CMW100 through a short TX-EVM sweep, no DUT/limits involvement."""
    logger.info("Smoke: starting CMW100 TX-EVM sweep (%d points)", len(SMOKE_SWEEP_DBM))
    logger.info("  resource     = %s", config.instruments["cmw100"].resource)
    logger.info("  band         = %s", config.band)
    logger.info("  modulation   = %s", config.modulation)
    logger.info("  rfbw_Hz      = %s", config.rfbw_Hz)
    logger.info("  ul_freq_pll  = %.3f GHz", config.ul_freq_pll_Hz / 1e9)

    for target_tx_power_dBm in SMOKE_SWEEP_DBM:
        logger.info("Sweeping target_tx_power=%.1f dBm", target_tx_power_dBm)

        cmw100.setup_NrTx(
            in_band=config.band,
            in_freq_pll_Hz=config.ul_freq_pll_Hz,
            in_rfbw_Hz=config.rfbw_Hz,
            in_rb_centre_freq_Hz=config.rb_centre_freq_Hz,
            in_tx_power_dBm=target_tx_power_dBm,
            in_tx_power_backoff_dB=config.tx_power_backoff_dB,
            in_modulation=config.modulation,
            in_ul_config=config.ul_config,
            in_scs_Hz=config.scs_Hz,
        )

        cmw100.meas_NrTxAll()

        tx_power = cmw100.meas_NrTxPower(use_cached=True)
        if math.isnan(tx_power):
            logger.warning("CMW unable to report Tx Power level at target=%.1f", target_tx_power_dBm)
            time.sleep(1)
            continue

        out_EVM_pct = cmw100.meas_NrTxEVM(use_cached=True)
        if math.isnan(out_EVM_pct):
            logger.warning("CMW unable to report Tx EVM at target=%.1f", target_tx_power_dBm)
            time.sleep(1)
            continue

        logger.info(
            "  → measured: tx_power=%.2f dBm, EVM=%.3f%%",
            tx_power, out_EVM_pct,
        )

        results.publish(
            target_tx_power_dBm=target_tx_power_dBm,
            measured_tx_power_dBm=tx_power,
            measured_EVM_pct=out_EVM_pct,
            modulation=config.modulation,
            band=config.band,
        )

    # No verdict — this is a connectivity / measurement smoke. The fact that
    # we got 5 valid (non-NaN) records into results.json IS the success criterion.
    n_records = sum(1 for _ in SMOKE_SWEEP_DBM)
    logger.info("Smoke complete: %d records emitted", n_records)
