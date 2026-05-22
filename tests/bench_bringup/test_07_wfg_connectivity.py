"""07 — WFG connectivity smoke. *IDN? + error queue.

PURPOSE
  Confirms the LAN + Keysight 33500B waveform generator + pyvisa chain
  is healthy.

USAGE
  uv run pytest tests/bench_bringup/test_07_wfg_connectivity.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=07-wfg.json --log-cli-level=INFO -v

EXPECTED OUTPUT
  INFO  WFG *IDN? -> Keysight Technologies,33522B,...
  INFO  WFG SYST:ERR? -> 0,"No error"
  PASSED
"""
from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.testcase("WFG-CONNECTIVITY")
def test_wfg_identify_only(wfg, results):
    """Confirm WFG session opens and *IDN? round-trips cleanly."""
    idn = wfg.identify()
    logger.info("WFG *IDN? -> %s", idn)
    results.publish(idn=idn)

    errs = wfg.drain_errors()
    logger.info("WFG error queue -> %s", errs or "<clean>")
    results.publish(pending_errors=errs)
    assert not errs, f"WFG has pending errors: {errs}"
