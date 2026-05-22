"""03 — CMW100 TX-EVM 5-point smoke sweep. No DUT, no calibration data.

PURPOSE
  Confirms the full CMW100 NR FR1 Meas measurement chain works on the bench:
    - configure NR Tx for a band/modulation/bandwidth
    - trigger meas_NrTxAll
    - fetch tx_power + EVM
    - 5 sweep points, ~seconds total

USAGE
  uv run pytest tests/bench_bringup/test_03_cmw100_tx_evm_smoke.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=03-smoke.json \\
      --log-cli-level=INFO -v

EXPECTED
  5 records in 03-smoke.json with measured tx_power + EVM. The TEST passes
  as long as no exception is raised. (NaN measurements are logged but do
  NOT fail the test — that condition still proves the SCPI path works,
  just no signal at the port.)

KNOWN FAILURE MODE
  "Header suffix out of range" -> NR FR1 Meas app not instantiated.
  Run test_02_cmw100_nr_diagnostics.py to diagnose.

NOT REQUIRED for this test
  - DUT, DMM, WFG (fixtures not requested)
  - Calibration / deembedding / limits YAML files (not loaded)
"""
from __future__ import annotations

import logging
import math
import time

import pytest

TESTCASE_ID = "CMW100-TX-EVM-SMOKE"
SMOKE_SWEEP_DBM = [-30.0, -20.0, -10.0, 0.0, 10.0]

logger = logging.getLogger(__name__)


@pytest.mark.testcase(TESTCASE_ID)
def test_cmw100_tx_evm_smoke(cmw100, config, results):
    """5-point TX-EVM sweep against real CMW100."""
    logger.info("Smoke: starting CMW100 TX-EVM sweep (%d points)", len(SMOKE_SWEEP_DBM))
    logger.info("  resource     = %s", config.instruments["cmw100"].resource)
    logger.info("  band         = %s", config.band)
    logger.info("  modulation   = %s", config.modulation)
    logger.info("  rfbw_Hz      = %s", config.rfbw_Hz)
    logger.info("  ul_freq_pll  = %.3f GHz", config.ul_freq_pll_Hz / 1e9)

    n_emitted = 0
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
            logger.warning("CMW unable to report Tx Power at target=%.1f", target_tx_power_dBm)
            time.sleep(1)
            continue

        out_EVM_pct = cmw100.meas_NrTxEVM(use_cached=True)
        if math.isnan(out_EVM_pct):
            logger.warning("CMW unable to report Tx EVM at target=%.1f", target_tx_power_dBm)
            time.sleep(1)
            continue

        logger.info("  -> measured: tx_power=%.2f dBm, EVM=%.3f%%", tx_power, out_EVM_pct)
        results.publish(
            target_tx_power_dBm=target_tx_power_dBm,
            measured_tx_power_dBm=tx_power,
            measured_EVM_pct=out_EVM_pct,
            modulation=config.modulation,
            band=config.band,
        )
        n_emitted += 1

    logger.info("Smoke complete: %d/%d records emitted", n_emitted, len(SMOKE_SWEEP_DBM))
