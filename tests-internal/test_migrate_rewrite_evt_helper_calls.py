"""Tests for the RewriteEvtHelperCalls transformer.

OpenTAP U300_RFEngine_EVT_Base TestStep base class exposed three helpers
that subclasses called as instance methods:

    self.Setup_DMM()
    self.Get_DMM()
    self.Get_Aux()

After ConvertClassToTestFunction strips ``self.``, those become bare
``Setup_DMM()`` / ``Get_DMM()`` / ``Get_Aux()`` calls — undefined names
at module scope.

V1c-7 ported the helpers to module-level functions in
``openflow.rfengine.evt_base`` (lowercase: ``setup_dmm``, ``get_dmm``,
``get_aux``). This transformer closes the last manual step by:

  1. Renaming each call (case-fix + arg-stub for required ``dmms`` /
     ``dut`` parameters).
  2. Injecting ``from openflow.rfengine.evt_base import ...`` for
     whichever names actually appear in the rewritten code.

The ``dmms={}`` placeholder is intentional — the bench-specific DMM
mapping is engineer judgment. An empty dict makes the call runtime-safe
(no TypeError) and visible (zero readings); the engineer fills in
``dmms={\"dmm_c\": dmm_c, ...}`` for their wiring.
"""
from openflow.migrate.transformers import RewriteEvtHelperCalls, transform


def test_rewrites_setup_dmm_call():
    before = "def test_x(dut):\n    Setup_DMM()\n"
    after = transform(before, RewriteEvtHelperCalls())
    assert "setup_dmm(dmms={})" in after
    assert "Setup_DMM" not in after


def test_rewrites_get_dmm_call():
    before = "def test_x(dut):\n    Get_DMM()\n"
    after = transform(before, RewriteEvtHelperCalls())
    assert "get_dmm(dmms={})" in after
    assert "Get_DMM" not in after


def test_rewrites_get_aux_call():
    before = "def test_x(dut):\n    Get_Aux()\n"
    after = transform(before, RewriteEvtHelperCalls())
    assert "get_aux(dut)" in after
    assert "Get_Aux" not in after


def test_injects_import_for_used_helpers_only():
    before = "def test_x(dut):\n    Setup_DMM()\n    Get_Aux()\n"
    after = transform(before, RewriteEvtHelperCalls())
    # Both names imported, get_dmm NOT (it's unused).
    assert "from openflow.rfengine.evt_base import" in after
    assert "setup_dmm" in after.split("from openflow.rfengine.evt_base import")[1].split("\n")[0]
    assert "get_aux" in after.split("from openflow.rfengine.evt_base import")[1].split("\n")[0]
    assert "get_dmm" not in after.split("from openflow.rfengine.evt_base import")[1].split("\n")[0]


def test_no_import_when_no_helpers_used():
    before = "def test_x():\n    return 42\n"
    after = transform(before, RewriteEvtHelperCalls())
    assert "openflow.rfengine.evt_base" not in after


def test_preserves_call_with_existing_args():
    """If someone wrote Setup_DMM(some_arg), keep the arg; just rename."""
    # Original OpenTAP form took no args (used self.dmm_*), but defensive.
    before = "def test_x(dut):\n    Setup_DMM(dmms={'dmm_c': dmm_c})\n"
    after = transform(before, RewriteEvtHelperCalls())
    # Already had explicit dmms — preserve it, just rename the function.
    assert "setup_dmm(dmms={'dmm_c': dmm_c})" in after
    assert "Setup_DMM" not in after


def test_leaves_attribute_calls_alone():
    """If someone wrote obj.Setup_DMM(), don't rewrite — could be a real
    method on a different object that happens to share the name."""
    before = "def test_x(obj):\n    obj.Setup_DMM()\n"
    after = transform(before, RewriteEvtHelperCalls())
    assert "obj.Setup_DMM()" in after
    # No import should be injected because no bare-name call was rewritten.
    assert "openflow.rfengine.evt_base" not in after


def test_handles_multiple_calls_to_same_helper():
    """Multiple Setup_DMM() calls in the same function — all renamed,
    single import injected."""
    before = (
        "def test_x(dut):\n"
        "    Setup_DMM()\n"
        "    for x in [1, 2]:\n"
        "        Setup_DMM()\n"
    )
    after = transform(before, RewriteEvtHelperCalls())
    assert after.count("setup_dmm(dmms={})") == 2
    assert after.count("Setup_DMM") == 0
    assert after.count("from openflow.rfengine.evt_base import setup_dmm") == 1


def test_does_not_duplicate_existing_import():
    """If the migrated source already imports setup_dmm, don't add it again."""
    before = (
        "from openflow.rfengine.evt_base import setup_dmm\n"
        "\n"
        "def test_x(dut):\n"
        "    Setup_DMM()\n"
    )
    after = transform(before, RewriteEvtHelperCalls())
    # Only one import line for setup_dmm.
    assert after.count("from openflow.rfengine.evt_base import setup_dmm") == 1
    assert "setup_dmm(dmms={})" in after
