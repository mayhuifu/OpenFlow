"""02 — Diagnose why NRSub:MEASurement<N> commands fail (if they do).

PURPOSE
  Run this if test_03_cmw100_tx_evm_smoke.py (or any NR-related test) fails
  with "Header suffix out of range" or similar SCPI errors. Dumps everything
  needed to determine whether:
    - The NR FR1 Meas software option is licensed on this CMW100
    - The NR measurement application is instantiated
    - The current INSTrument:SELect points at NR or something else

  No assertions — always passes. Read the SUMMARY block at the end of
  the log to interpret.

USAGE
  uv run pytest tests/bench_bringup/test_02_cmw100_nr_diagnostics.py \\
      --openflow-config=tests/configs/u300b0_evt.yaml \\
      --openflow-report=02-diag.json \\
      --log-cli-level=INFO -v

INTERPRETING THE OUTPUT
  - "NR options" empty (no "NR" in *OPT?) -> CMW100 lacks the license.
  - "Current app" is something non-NR -> framework needs to add
    INSTrument:CREate "<NR app name>" to CMW100.open() before any setup_NrTx.
  - "NRSub probe" returns a value cleanly -> NR app is active, the
    -114 error must be coming from something else specific to setup_NrTx.
"""
from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


def _query(cmw100, scpi: str) -> str:
    val = cmw100.cmwa.Base.utilities.query_str(scpi)
    logger.info("Q  %-40s -> %s", scpi, val)
    return val


def _drain_errors(cmw100) -> list[str]:
    errs = []
    for _ in range(20):
        err = cmw100.cmwa.Base.utilities.query_str("SYSTem:ERRor?")
        if err.startswith("0,") or err.startswith("+0,") or '"No error"' in err:
            break
        errs.append(err)
    return errs


@pytest.mark.testcase("CMW100-NR-DIAG")
def test_cmw100_nr_diagnostics(cmw100, results):
    """No assertions — dumps everything useful to log + report."""
    # ----------------------------------------------- 1. Identity / options
    idn = _query(cmw100, "*IDN?")
    options = _query(cmw100, "*OPT?")
    nr_options = [opt for opt in options.split(",") if "NR" in opt.upper()]
    logger.info("NR-related options: %s", nr_options or "<none found>")

    # ----------------------------------------------- 2. App catalog
    try:
        app_list = _query(cmw100, "INSTrument:LIST?")
    except Exception as e:
        app_list = f"<query failed: {e}>"
    try:
        current_app = _query(cmw100, "INSTrument:SELect?")
    except Exception as e:
        current_app = f"<query failed: {e}>"

    # ----------------------------------------------- 3. Probe NRSub chain
    try:
        cmw100.cmwa.Base.utilities.write_str("*CLS")  # clear stale errors
        probe = _query(cmw100, "ROUTe:NRSub:MEASurement:SCENario?")
    except Exception as e:
        probe = f"<query failed: {e}>"
    probe_errs = _drain_errors(cmw100)
    logger.info("Errors after NRSub probe: %s", probe_errs or "<none>")

    # ----------------------------------------------- 4. Publish + summary
    results.publish(
        idn=idn,
        all_options=options,
        nr_options=nr_options,
        application_list=app_list,
        current_application=current_app,
        nrsub_probe=probe,
        nrsub_probe_errors=probe_errs,
    )

    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("  IDN:           %s", idn)
    logger.info("  *OPT? (full):  %s", options)
    logger.info("  NR options:    %s", nr_options or "<NONE — likely no license>")
    logger.info("  App list:      %s", app_list)
    logger.info("  Current app:   %s", current_app)
    logger.info("  NRSub probe:   %s", probe)
    logger.info("  NRSub errors:  %s", probe_errs or "<clean>")
    logger.info("=" * 60)
