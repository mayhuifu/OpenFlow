"""Tests for the RewriteSweepLoops transformer.

V2: lift simple outer `for x in iterable:` loops whose body has no
per-iteration setup side effects into ``@pytest.mark.parametrize``
decorators on the enclosing test function.

The heuristic is deliberately strict: a loop is liftable iff:

- the iterable is a literal list / tuple, a ``range(...)`` call, or a
  ``np.arange(...)`` call (known-pure factories)
- the loop body contains no calls to methods on instrument fixtures
  (``dut.*``, ``cmw100.*``, ``wfg.*``, ``sg.*``, ``sa.*``, ``dmm_c.*``,
  ``dmm_v.*``) — those are setup side effects
- the loop is the outermost statement in the test function body, OR
  the only non-trivial statement at its level

If a loop doesn't match, we leave it alone — the engineer's nested
loop with setup side effects stays as a runtime loop. Only the
"obvious" sweeps lift.
"""
from openflow.migrate.transformers import RewriteSweepLoops, transform


def test_lifts_simple_outer_for_to_parametrize():
    before = (
        "def test_x(results):\n"
        "    for gain in [0, 3, 6, 9]:\n"
        "        results.publish(gain=gain)\n"
    )
    after = transform(before, RewriteSweepLoops())
    assert "@pytest.mark.parametrize" in after
    assert "gain" in after
    # Must add gain to the function signature.
    assert "test_x(results, gain)" in after
    # Loop must be gone.
    assert "for gain in" not in after


def test_lifts_with_np_arange_iterable():
    before = (
        "def test_x(results):\n"
        "    for p in np.arange(-45, 28+1, 1.0):\n"
        "        results.publish(power=p)\n"
    )
    after = transform(before, RewriteSweepLoops())
    assert "@pytest.mark.parametrize" in after
    assert "np.arange(-45, 28+1, 1.0)" in after


def test_lifts_with_range_iterable():
    before = (
        "def test_x(results):\n"
        "    for i in range(10):\n"
        "        results.publish(i=i)\n"
    )
    after = transform(before, RewriteSweepLoops())
    assert "@pytest.mark.parametrize" in after
    assert "range(10)" in after


def test_leaves_loops_with_dut_calls_alone():
    """A loop body that calls dut.set_*() has per-iteration setup
    side effects — must stay as a runtime loop."""
    before = (
        "def test_x(dut, results):\n"
        "    for gain in [0, 3]:\n"
        "        dut.set_rfRxGain(gain)\n"
        "        results.publish(gain=gain)\n"
    )
    after = transform(before, RewriteSweepLoops())
    assert "for gain in" in after  # loop remains
    assert "@pytest.mark.parametrize" not in after


def test_leaves_loops_with_cmw100_calls_alone():
    before = (
        "def test_x(cmw100, results):\n"
        "    for f in [2.0e9, 2.5e9]:\n"
        "        cmw100.set_rf_power(0)\n"
        "        results.publish(f=f)\n"
    )
    after = transform(before, RewriteSweepLoops())
    assert "for f in" in after
    assert "@pytest.mark.parametrize" not in after


def test_leaves_nested_loops_alone():
    """Nested loops are common in EVT tests with modulation x power sweeps.
    The conservative behavior is to leave them alone; engineer hand-lifts
    if they want both as parametrize (and stacks the decorators)."""
    before = (
        "def test_x(results):\n"
        "    for m in ['QPSK', '16QAM']:\n"
        "        for p in [0, 3]:\n"
        "            results.publish(m=m, p=p)\n"
    )
    after = transform(before, RewriteSweepLoops())
    # Inner loop has no instrument calls but contains another loop —
    # the outer loop's body isn't simple enough to lift.
    assert "for m in" in after
    assert "for p in" in after


def test_leaves_loops_with_assignments_other_than_publish():
    """A loop with non-publish assignments may be doing real work —
    don't lift."""
    before = (
        "def test_x(results):\n"
        "    for x in [1, 2, 3]:\n"
        "        y = x * 2\n"
        "        results.publish(y=y)\n"
    )
    after = transform(before, RewriteSweepLoops())
    # `y = x * 2` is a computation that wouldn't trivially survive
    # parametrize lift. Leave alone.
    assert "for x in" in after


def test_preserves_function_decorators_above_parametrize():
    """If the test function already has decorators (e.g. @pytest.mark.testcase),
    new parametrize decorator stacks above the existing ones."""
    before = (
        "@pytest.mark.testcase('TC1')\n"
        "def test_x(results):\n"
        "    for gain in [0, 3]:\n"
        "        results.publish(gain=gain)\n"
    )
    after = transform(before, RewriteSweepLoops())
    assert "@pytest.mark.parametrize" in after
    assert "@pytest.mark.testcase('TC1')" in after


def test_multiple_simple_outer_loops_in_same_function_only_lifts_first():
    """If the function has two top-level loops, lifting both creates a
    cartesian product that may not match the engineer's intent. Conservative:
    lift only the first."""
    before = (
        "def test_x(results):\n"
        "    for g in [0, 3]:\n"
        "        results.publish(g=g)\n"
        "    for p in [10, 20]:\n"
        "        results.publish(p=p)\n"
    )
    after = transform(before, RewriteSweepLoops())
    # First lifted, second left.
    assert "@pytest.mark.parametrize" in after
    assert "for p in" in after  # second loop survives


def test_leaves_functions_without_for_alone():
    before = "def test_x(results):\n    results.publish(value=1)\n"
    after = transform(before, RewriteSweepLoops())
    assert "@pytest.mark.parametrize" not in after
    assert "test_x(results)" in after
