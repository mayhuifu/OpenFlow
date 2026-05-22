"""05 — SG connectivity smoke. *IDN? + error queue.

PURPOSE
  Confirms the LAN + R&S SMW200A signal generator + pyvisa chain is healthy.

USAGE
  uv run pytest tests/bench_bringup/test_05_sg_connectivity.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=05-sg.json --log-cli-level=INFO -v

EXPECTED OUTPUT
  INFO  SG *IDN? -> Rohde&Schwarz,SMW200A,...
  INFO  SG SYST:ERR? -> 0,"No error"
  PASSED
"""
from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.testcase("SG-CONNECTIVITY")
def test_sg_identify_only(sg, results):
    """Confirm SG session opens and *IDN? round-trips cleanly."""
    idn = sg.identify()
    logger.info("SG *IDN? -> %s", idn)
    results.publish(idn=idn)

    errs = sg.drain_errors()
    logger.info("SG error queue -> %s", errs or "<clean>")
    results.publish(pending_errors=errs)
    assert not errs, f"SG has pending errors: {errs}"
