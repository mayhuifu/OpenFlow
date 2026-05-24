"""03c — Diagnose why CMW100 LTE SCPI returns -114 even with MEASurement1 suffix.

PURPOSE
  Bench engineer at SZLABPC-WIN04 hit:
    -114,"Header suffix out of range;CONFigure:LTE:MEASurement1:MEValuation:DMODe FDD"

  The MEASurement1 suffix didn't fix it. This test probes every plausible
  hypothesis about what's wrong on this CMW100 (firmware 3.8.17):

    1. Is an LTE Meas application instantiated?
    2. If not, does INSTrument:CREate work? With which app name?
    3. After INSTrument:SELect "LTE Meas <X>", does the LTE config command succeed?
    4. Do any SCPI variants work (LTE:MEAS / LTE:MEASurement / LTE:MEASurement1 / etc.)?
    5. What does the Python LTE SDK (RsCmwLteMeas) generate when called directly?

  No assertions — always passes. Read the SUMMARY block at the end of the
  log to determine which fix the framework needs.

USAGE
  uv run pytest tests/bench_bringup/test_03c_cmw100_lte_diagnostics.py \
      --openflow-config=tests/configs/u300b0_evt.yaml \
      --openflow-report=reports/03c-lte-diag.json \
      --log-cli-level=INFO -v

INTERPRETING THE OUTPUT
  - If "LTE Meas instantiation" succeeds and afterwards the LTE config
    SCPI also succeeds, the framework needs to add INSTrument:CREate /
    SELect to CMW100.open() or setup_LteTx().
  - If LTE SDK methods succeed but raw SCPI fails, switch to SDK methods
    in the mixin (mirroring how CMW100AMixin uses RsCmwNrFr1Meas).
  - If both raw SCPI + SDK methods fail, the bench CMW100 may need a
    firmware upgrade or has a different LTE meas application name than
    we expect.
"""
from __future__ import annotations

import logging

import pytest

logger = logging.getLogger(__name__)


def _query(cmw100, scpi: str) -> str:
    """Direct query via the Base SDK utilities. May raise on instrument errors."""
    val = cmw100.cmwa.Base.utilities.query_str(scpi)
    logger.info("Q  %-60s -> %s", scpi, val)
    return val


def _try_query(cmw100, scpi: str) -> str:
    """Tolerant query — returns the error text instead of raising."""
    try:
        return _query(cmw100, scpi)
    except Exception as exc:
        msg = f"<query failed: {exc}>"
        logger.info("Q  %-60s -> %s", scpi, msg)
        return msg


def _try_write(cmw100, scpi: str) -> str:
    """Tolerant write — returns 'OK' on success, error text otherwise."""
    try:
        cmw100.cmwa.Base.utilities.write_str(scpi)
        logger.info("W  %-60s -> OK", scpi)
        return "OK"
    except Exception as exc:
        msg = f"<write failed: {exc}>"
        logger.info("W  %-60s -> %s", scpi, msg)
        # Clear so subsequent commands don't see this error.
        try:
            cmw100.cmwa.Base.utilities.write_str("*CLS")
        except Exception:
            pass
        return msg


def _drain_errors(cmw100, max_iters: int = 20) -> list[str]:
    """Drain the CMW100 error queue."""
    errs = []
    for _ in range(max_iters):
        try:
            err = cmw100.cmwa.Base.utilities.query_str("SYSTem:ERRor?")
        except Exception as exc:
            errs.append(f"<error queue query failed: {exc}>")
            break
        if err.startswith("0,") or err.startswith("+0,") or '"No error"' in err:
            break
        errs.append(err)
    return errs


@pytest.mark.testcase("CMW100-LTE-DIAG")
def test_cmw100_lte_diagnostics(cmw100, results):
    """No assertions — dumps everything useful for diagnosing why
    CONFigure:LTE:... is failing with -114 on this CMW100 firmware."""

    # 1. Baseline state
    logger.info("=" * 70)
    logger.info("PHASE 1: baseline instrument state")
    logger.info("=" * 70)
    idn = _try_query(cmw100, "*IDN?")
    opt = _try_query(cmw100, "*OPT?")
    has_km500 = "KM500" in opt
    logger.info("Has KM500 (LTE Meas option): %s", has_km500)

    initial_app = _try_query(cmw100, "INSTrument:SELect?")
    initial_list = _try_query(cmw100, "INSTrument:LIST?")
    _drain_errors(cmw100)  # clear any errors from the probes

    # 2. Try to instantiate an LTE Meas application
    logger.info("=" * 70)
    logger.info("PHASE 2: try to instantiate an LTE Meas application")
    logger.info("=" * 70)
    create_attempts = [
        'INSTrument:CREate:NAME "LTE Meas 1", "LTE Meas"',
        'INSTrument:CREate "LTE Meas 1", "LTE Meas"',
        'INSTrument:CREate "LTE Meas 1"',
        'INSTrument:CREate:NAME "LTE Meas", "LTE Meas"',
    ]
    create_results: list[tuple[str, str, str]] = []
    for cmd in create_attempts:
        result = _try_write(cmw100, cmd)
        post_select = _try_query(cmw100, "INSTrument:SELect?")
        create_results.append((cmd, result, post_select))
        _drain_errors(cmw100)

    # 3. Try to select an LTE Meas application
    logger.info("=" * 70)
    logger.info("PHASE 3: try to select an LTE Meas application")
    logger.info("=" * 70)
    select_attempts = [
        'INSTrument:SELect "LTE Meas 1"',
        'INSTrument:SELect "LTE Meas"',
        'INSTrument:SELect "LTE"',
    ]
    select_results: list[tuple[str, str, str]] = []
    for cmd in select_attempts:
        result = _try_write(cmw100, cmd)
        post_select = _try_query(cmw100, "INSTrument:SELect?")
        select_results.append((cmd, result, post_select))
        _drain_errors(cmw100)

    # 4. Try various forms of the LTE config command
    logger.info("=" * 70)
    logger.info("PHASE 4: try various forms of CONFigure:LTE:...:DMODe")
    logger.info("=" * 70)
    config_attempts = [
        "CONFigure:LTE:MEASurement1:MEValuation:DMODe FDD",
        "CONFigure:LTE:MEASurement:MEValuation:DMODe FDD",
        "CONFigure:LTE:MEAS1:MEValuation:DMODe FDD",
        "CONFigure:LTE:MEAS:MEValuation:DMODe FDD",
        "CONFigure:LTE:MEASurement1:MEValuation1:DMODe FDD",
        "CONFigure:LTE:MEValuation:DMODe FDD",  # without MEASurement?
        # Also try query variants — these might reveal the right tree
        "CONFigure:LTE:MEASurement1:MEValuation:DMODe?",
        "CONFigure:LTE:MEASurement1:RFSettings:FREQuency?",
    ]
    config_results: list[tuple[str, str]] = []
    for cmd in config_attempts:
        if cmd.endswith("?"):
            result = _try_query(cmw100, cmd)
        else:
            result = _try_write(cmw100, cmd)
        config_results.append((cmd, result))
        _drain_errors(cmw100)

    # 5. Try LTE SDK methods (mirrors how CMW100AMixin uses the NR SDK)
    logger.info("=" * 70)
    logger.info("PHASE 5: probe the RsCmwLteMeas SDK surface")
    logger.info("=" * 70)
    sdk_results: list[tuple[str, str]] = []
    try:
        lte_sdk = cmw100.cmwa.LteMeas
        if lte_sdk is None:
            sdk_results.append(("LteMeas session", "<None — SDK not initialized>"))
        else:
            # Probe SDK attribute paths
            for attr_path in [
                "configure",
                "configure.multiEval",
                "configure.multiEval.set_dmode",
                "route",
                "route.rfSettings",
                "configure.rfSettings",
                "configure.rfSettings.set_eattenuation",
            ]:
                try:
                    obj = lte_sdk
                    for part in attr_path.split("."):
                        obj = getattr(obj, part)
                    sdk_results.append((attr_path, f"<exists: {type(obj).__name__}>"))
                except AttributeError as exc:
                    sdk_results.append((attr_path, f"<missing: {exc}>"))
    except Exception as exc:
        sdk_results.append(("(top-level)", f"<error: {exc}>"))

    # 6. SUMMARY block
    logger.info("=" * 70)
    logger.info("SUMMARY — paste this whole block when reporting the result")
    logger.info("=" * 70)
    logger.info("  IDN:           %s", idn)
    logger.info("  *OPT?:         %s", opt)
    logger.info("  Has KM500:     %s", has_km500)
    logger.info("  Initial app:   %s", initial_app)
    logger.info("  INSTrument:LIST?: %s", initial_list)
    logger.info("")
    logger.info("  -- INSTrument:CREate attempts --")
    for cmd, result, post_sel in create_results:
        logger.info("    %s", cmd)
        logger.info("       -> %s", result)
        logger.info("       -> SELect? = %s", post_sel)
    logger.info("")
    logger.info("  -- INSTrument:SELect attempts --")
    for cmd, result, post_sel in select_results:
        logger.info("    %s", cmd)
        logger.info("       -> %s", result)
        logger.info("       -> SELect? = %s", post_sel)
    logger.info("")
    logger.info("  -- CONFigure:LTE:... attempts --")
    for cmd, result in config_results:
        logger.info("    %s", cmd)
        logger.info("       -> %s", result)
    logger.info("")
    logger.info("  -- RsCmwLteMeas SDK attributes --")
    for attr_path, status in sdk_results:
        logger.info("    %-50s %s", attr_path, status)
    logger.info("=" * 70)

    results.publish(
        idn=idn,
        opt=opt,
        has_km500=has_km500,
        initial_app=initial_app,
        initial_list=initial_list,
        create_attempts=[{"cmd": c, "result": r, "post_select": p}
                         for c, r, p in create_results],
        select_attempts=[{"cmd": c, "result": r, "post_select": p}
                         for c, r, p in select_results],
        config_attempts=[{"cmd": c, "result": r} for c, r in config_results],
        sdk_attributes=[{"path": p, "status": s} for p, s in sdk_results],
    )
