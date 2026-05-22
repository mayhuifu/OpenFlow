"""06 — SA connectivity smoke. *IDN? + error queue.

PURPOSE
  Confirms the LAN + spectrum analyzer (Keysight N9020B by default, or
  R&S FSW if instruments.sa.model: rs_fsw is set in the YAML) + pyvisa
  chain is healthy.

USAGE
  uv run pytest tests/bench_bringup/test_06_sa_connectivity.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=06-sa.json --log-cli-level=INFO -v

EXPECTED OUTPUT (Keysight default)
  INFO  SA *IDN? -> Keysight Technologies,N9020B,...
  INFO  SA SYST:ERR? -> 0,"No error"
  PASSED
"""
from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.testcase("SA-CONNECTIVITY")
def test_sa_identify_only(sa, results):
    """Confirm SA session opens and *IDN? round-trips cleanly."""
    idn = sa.identify()
    logger.info("SA *IDN? -> %s", idn)
    results.publish(idn=idn)

    errs = sa.drain_errors()
    logger.info("SA error queue -> %s", errs or "<clean>")
    results.publish(pending_errors=errs)
    assert not errs, f"SA has pending errors: {errs}"
