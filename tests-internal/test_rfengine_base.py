"""Tests for openflow.rfengine.base helpers.

V1f promotes the previously-inlined ``_initialize_tx`` stub from
``tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py`` into a proper
module-level ``initialize_tx`` function. Real-hardware behavior is
delegated to the DUT methods (``cmd_initialize`` + ``set_rfTxPower``);
this module just owns the orchestration of the two calls.

The original OpenTAP ``initialize_tx`` lived as an instance method on
``U300_RFEngine_Base`` and combined:
  1. optional reboot of the RFIC + RFFE
  2. setting Tx power to a target value
  3. returning the achieved power + DAC backoff

We preserve the same shape as a free function so migrated tests can
``from openflow.rfengine.base import initialize_tx`` without needing
an instance.
"""
from openflow.dut.u300 import DUT_U300
from openflow.rfengine.base import initialize_tx


def _make_emul_dut() -> DUT_U300:
    d = DUT_U300()
    d.emulation = True
    return d


def test_returns_tuple_of_pwr_and_dac_backoff():
    d = _make_emul_dut()
    result = initialize_tx(d, target_tx_power=10.0)
    assert isinstance(result, tuple)
    assert len(result) == 2
    pwr, backoff = result
    assert isinstance(pwr, float)
    assert isinstance(backoff, float)


def test_emulation_returns_target_power_and_zero_backoff():
    """DUT_U300 emulation: set_rfTxPower returns (target, -1, -1, 0.0).
    initialize_tx should propagate the (pwr, dac_bo) pair unchanged."""
    d = _make_emul_dut()
    pwr, dac_bo = initialize_tx(d, target_tx_power=15.0)
    assert pwr == 15.0
    assert dac_bo == 0.0


def test_force_reboot_calls_cmd_initialize():
    """With force_reboot=True, initialize_tx must call dut.cmd_initialize
    before setting power. We verify by counting cmd_initialize invocations."""
    class CountingDut(DUT_U300):
        def __init__(self) -> None:
            super().__init__()
            self.emulation = True
            self.cmd_initialize_calls = 0

        def cmd_initialize(self, **kwargs):  # type: ignore[override]
            self.cmd_initialize_calls += 1
            return super().cmd_initialize(**kwargs)

    d = CountingDut()
    initialize_tx(d, target_tx_power=0.0, force_reboot=True)
    assert d.cmd_initialize_calls == 1


def test_no_force_reboot_skips_cmd_initialize():
    class CountingDut(DUT_U300):
        def __init__(self) -> None:
            super().__init__()
            self.emulation = True
            self.cmd_initialize_calls = 0

        def cmd_initialize(self, **kwargs):  # type: ignore[override]
            self.cmd_initialize_calls += 1
            return super().cmd_initialize(**kwargs)

    d = CountingDut()
    initialize_tx(d, target_tx_power=0.0)  # force_reboot defaults to False
    assert d.cmd_initialize_calls == 0


def test_propagates_set_rfTxPower_NotImplementedError_on_bench():
    """Bench DUT_U300.set_rfTxPower raises NotImplementedError (V1f audit).
    initialize_tx must NOT swallow it — the engineer needs to see the
    failure with the helpful message."""
    import pytest

    d = DUT_U300()
    d.emulation = False
    with pytest.raises(NotImplementedError, match="set_rfTxPower"):
        initialize_tx(d, target_tx_power=0.0)


def test_force_reboot_failure_propagates():
    """If cmd_initialize raises (V1f bench behavior), initialize_tx must
    propagate the error, not swallow it. The previous test-file stub
    swallowed with a warning; the real port should fail loudly."""
    import pytest

    d = DUT_U300()
    d.emulation = False
    with pytest.raises(NotImplementedError, match="cmd_initialize"):
        initialize_tx(d, target_tx_power=0.0, force_reboot=True)
