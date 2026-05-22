"""04 — DMM connectivity smoke. *IDN? + error queue.

PURPOSE
  Confirms the LAN + Keysight 34461A DMM + pyvisa chain is healthy.
  V1f shipped the real driver; V3 adds this bring-up test.

USAGE
  uv run pytest tests/bench_bringup/test_04_dmm_connectivity.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=04-dmm.json --log-cli-level=INFO -v

EXPECTED OUTPUT
  INFO  DMM (dmm_c) *IDN? -> Keysight Technologies,34461A,...
  INFO  DMM (dmm_c) SYST:ERR? -> 0,"No error"
  PASSED

NOT REQUIRED for this test
  - DUT, CMW100 (fixtures not requested)
  - SG, SA, WFG (fixtures not requested)
"""
from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.testcase("DMM-CONNECTIVITY")
def test_dmm_c_identify_only(dmm_c, results):
    """Confirm dmm_c session opens and *IDN? round-trips cleanly."""
    idn = dmm_c.identify()
    logger.info("DMM (dmm_c) *IDN? -> %s", idn)
    results.publish(idn=idn)

    errs = dmm_c.drain_errors()
    logger.info("DMM (dmm_c) error queue -> %s", errs or "<clean>")
    results.publish(pending_errors=errs)
    assert not errs, f"DMM (dmm_c) has pending errors: {errs}"
