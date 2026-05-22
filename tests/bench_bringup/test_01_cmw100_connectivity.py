"""01 — CMW100 connectivity smoke. *IDN? + error queue only.

PURPOSE
  First test the bench engineer runs after `uv sync`. Confirms:
    - The R&S SDK installed correctly
    - The VISA resource string in the YAML points at a real CMW100
    - The CMW100 responds to *IDN? and has no pending errors

  No NR-specific config is touched here. If this passes, the LAN +
  framework + SDK chain is healthy.

USAGE
  uv run pytest tests/bench_bringup/test_01_cmw100_connectivity.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=01-conn.json \\
      --log-cli-level=INFO -v

EXPECTED OUTPUT
  INFO  CMW100 *IDN? -> Rohde&Schwarz,CMW,<order>/<serial>,<firmware>
  INFO  CMW100 SYST:ERR? -> 0,"No error"
  PASSED

NOT REQUIRED for this test
  - DUT (FTDI, U300 board) — fixture not requested
  - DMM, WFG, PSU, OSC, SG, SA stubs — fixture not requested
  - configs/limits/, configs/deembedding/, configs/calibration/ files
"""
from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.testcase("CMW100-CONNECTIVITY")
def test_cmw100_identify_only(cmw100, results):
    """Confirm the SDK can open a session and query *IDN? — nothing else."""
    # cmwa.Base is the rscmw-base session, populated during CMW100.open().
    assert cmw100.cmwa.Base is not None, "Base SDK session not initialized"

    idn = cmw100.cmwa.Base.utilities.query_str("*IDN?")
    logger.info("CMW100 *IDN? -> %s", idn)
    results.publish(idn=idn)

    # Drain the error queue. R&S returns '0,"No error"' when clean.
    errs: list[str] = []
    for _ in range(10):
        err = cmw100.cmwa.Base.utilities.query_str("SYSTem:ERRor?")
        logger.info("CMW100 SYST:ERR? -> %s", err)
        if err.startswith("0,") or err.startswith("+0,") or '"No error"' in err:
            break
        errs.append(err)
    results.publish(pending_errors=errs)
    assert not errs, f"CMW100 has pending errors: {errs}"
