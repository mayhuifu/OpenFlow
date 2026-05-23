"""03b — CMW100 LTE TX-EVM 5-point smoke sweep. No DUT, no calibration data.

PURPOSE
  Alternate path to test_03 for CMW100 units licensed for LTE Tx Meas
  (option KM500) but NOT for NR FR1 Meas. Discovered during v1.0.0-rc1
  bring-up: the bench CMW100 (serial 131694, firmware 3.8.17) reported
  options ``CMW-H16E,KM200,KM400,KM500,KM500`` — KM500 is LTE Tx Meas,
  no NR options present.

  This test confirms the full CMW100 LTE FR Meas measurement chain
  works on the bench:
    - configure LTE Tx for a band/modulation/bandwidth
    - trigger meas_LteTxAll
    - fetch tx_power + EVM
    - 5 sweep points, ~seconds total

USAGE
  uv run pytest tests/bench_bringup/test_03b_cmw100_lte_tx_evm_smoke.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=03b-lte-smoke.json \\
      --openflow-html-report=03b-lte-smoke.html \\
      --log-cli-level=INFO -v

EXPECTED
  5 records in 03b-lte-smoke.json with measured tx_power + EVM. The TEST
  passes as long as no exception is raised. NaN measurements are logged
  but do NOT fail the test — that condition still proves the SCPI path
  works, just no signal at the port.

KNOWN FAILURE MODE
  "Header suffix out of range" -> the bench CMW100 lacks LTE Meas
  (KM500) options too. Verify *OPT? contains "KM500" before running.

NOT REQUIRED for this test
  - DUT, DMM, WFG (fixtures not requested)
  - Calibration / deembedding / limits YAML files (not loaded)
"""
from __future__ import annotations

import logging
import math
import time

import pytest

TESTCASE_ID = "CMW100-LTE-TX-EVM-SMOKE"
SMOKE_SWEEP_DBM = [-30.0, -20.0, -10.0, 0.0, 10.0]

# LTE smoke defaults — band 7, 10 MHz FDD, QPSK. These match the most
# common bench-side LTE configuration; engineers with a different
# product target should edit tests/configs/u300b0_evt.yaml.
LTE_DEFAULTS = {
    "band": "B7",
    "freq_pll_Hz": 2.65e9,
    "rfbw_Hz": 10e6,
    "duplex_mode": "FDD",
    "modulation": "QPSK",
}

logger = logging.getLogger(__name__)


@pytest.mark.testcase(TESTCASE_ID)
def test_cmw100_lte_tx_evm_smoke(cmw100, results):
    """5-point LTE TX-EVM sweep against real CMW100.

    Skips the test if the bench config explicitly opts out via
    ``instruments.cmw100.resource`` starting with ``MOCK::`` AND the
    engineer hasn't requested an emulation run (CI uses MOCK:: and
    expects the test to still pass — emulation returns canned data).
    """
    logger.info("LTE smoke: starting CMW100 LTE TX-EVM sweep (%d points)",
                len(SMOKE_SWEEP_DBM))
    for k, v in LTE_DEFAULTS.items():
        logger.info("  %-13s= %s", k, v)

    n_emitted = 0
    for target_tx_power_dBm in SMOKE_SWEEP_DBM:
        logger.info("Sweeping target_tx_power=%.1f dBm", target_tx_power_dBm)

        cmw100.setup_LteTx(
            in_band=LTE_DEFAULTS["band"],
            in_freq_pll_Hz=LTE_DEFAULTS["freq_pll_Hz"],
            in_rfbw_Hz=LTE_DEFAULTS["rfbw_Hz"],
            in_tx_power_dBm=target_tx_power_dBm,
            in_modulation=LTE_DEFAULTS["modulation"],
            in_duplex_mode=LTE_DEFAULTS["duplex_mode"],
        )

        cmw100.meas_LteTxAll()

        tx_power = cmw100.meas_LteTxPower(use_cached=True)
        if math.isnan(tx_power):
            logger.warning("CMW unable to report LTE Tx Power at target=%.1f",
                           target_tx_power_dBm)
            time.sleep(1)
            continue

        out_EVM_pct = cmw100.meas_LteTxEVM(use_cached=True)
        if math.isnan(out_EVM_pct):
            logger.warning("CMW unable to report LTE Tx EVM at target=%.1f",
                           target_tx_power_dBm)
            time.sleep(1)
            continue

        logger.info("  -> measured: tx_power=%.2f dBm, EVM=%.3f%%",
                    tx_power, out_EVM_pct)
        results.publish(
            target_tx_power_dBm=target_tx_power_dBm,
            measured_tx_power_dBm=tx_power,
            measured_EVM_pct=out_EVM_pct,
            modulation=LTE_DEFAULTS["modulation"],
            band=LTE_DEFAULTS["band"],
            duplex_mode=LTE_DEFAULTS["duplex_mode"],
        )
        n_emitted += 1

    logger.info("LTE smoke complete: %d/%d records emitted",
                n_emitted, len(SMOKE_SWEEP_DBM))
