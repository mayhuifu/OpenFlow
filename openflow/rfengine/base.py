"""rfengine base helpers ported from ``U300_RFEngine_Base.py``.

In the OpenTAP source, the ``initialize_tx`` helper lived as an instance
method on the ``U300_RFEngine_Base`` TestStep base class so every Tx
test could share the RFIC reboot + power-set orchestration. With the
V1 pivot to bare-metal pytest there is no base class to inherit from —
the helper is exposed here as a module-level function that takes its
DUT handle as an argument.

Faithfulness notes:

* The original method took ``in_tx_power_dBm`` from the inherited
  input-property pool. We accept it as ``target_tx_power`` (the
  ``in_`` prefix is OpenTAP-specific and would just clutter the
  caller).

* The original method returned ``(pwr, backoff)`` where ``pwr`` was the
  achieved Tx power at the antenna and ``backoff`` was the DAC backoff
  the RFIC settled on. We preserve that shape — callers can unpack
  ``pwr, backoff = initialize_tx(...)`` exactly as in the migrated
  source.

* Error propagation: previously a V1b stub in
  ``tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py`` swallowed
  ``NotImplementedError`` from ``dut.cmd_initialize`` and warned. That
  was the right behavior when DUT_U300 silently no-op'd everything,
  but V1f makes the real-hardware methods raise loudly — and at that
  point swallowing them would mask the failure. This module
  propagates errors unchanged so the engineer sees the bench failure
  with the exact method that needs porting.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def initialize_tx(dut: Any, target_tx_power: float, *,
                  force_reboot: bool = False) -> tuple[float, float]:
    """Initialize the DUT's TX chain at a target power level.

    Args:
        dut: a DUT instance implementing ``cmd_initialize`` and
            ``set_rfTxPower``. In V1f the only concrete DUT is
            ``DUT_U300``; other DUTs can plug in if they expose the
            same method names.
        target_tx_power: target Tx power in dBm at the antenna port.
        force_reboot: if True, call ``dut.cmd_initialize(force_reboot=True)``
            before setting power. Use when the test starts from a
            cold state or needs to recover from a previous run. The
            default is False so per-iteration calls inside a sweep
            don't re-init the RFIC every step.

    Returns:
        ``(pwr, dac_bo)``: ``pwr`` is the achieved Tx power at the
        antenna (matches the target on emulation; reported by the
        RFIC on real hardware). ``dac_bo`` is the DAC backoff the
        RFIC settled on.

    Raises:
        NotImplementedError: if the DUT's ``cmd_initialize`` or
            ``set_rfTxPower`` methods aren't yet ported for the
            real-hardware path. Engineer should fix the underlying
            DUT method rather than catching here.
    """
    if force_reboot:
        logger.info("initialize_tx: force_reboot — calling dut.cmd_initialize()")
        dut.cmd_initialize(force_reboot=True)

    logger.info("initialize_tx: setting Tx power to %.2f dBm", target_tx_power)
    pwr, _rfic_lut_idx, _pa_lut_idx, dac_bo = dut.set_rfTxPower(
        ul_powers_dBm=target_tx_power)

    logger.info("initialize_tx: achieved pwr=%.2f dBm, dac_bo=%.2f dB",
                pwr, dac_bo)
    return float(pwr), float(dac_bo)
