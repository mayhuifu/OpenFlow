"""Tests for the RewriteClassDunderName transformer.

By the time this transformer runs, ConvertClassToTestFunction has already
collapsed the OpenTAP TestStep class into a module-level test function
AND stripped every `self.` prefix. So the input looks like:

    __class__.__name__   # was: self.__class__.__name__

A bare ``__class__`` reference inside a module-level function is a
NameError at runtime (the implicit ``__class__`` cell only exists inside
class methods). The transformer:

  1. Rewrites every ``__class__.__name__`` to a bare ``CLASS_NAME`` Name.
  2. If any rewrite happened, injects a module-level
     ``CLASS_NAME = \"<OriginalClass>\"`` assignment near the top.

It does NOT rediscover the class name from the tree (the class is already
gone). The constructor takes ``class_name`` as a string — captured during
Phase 1 by a separate ``CaptureClassName`` transformer.
"""
from openflow.migrate.transformers import (
    CaptureClassName,
    RewriteClassDunderName,
    transform,
)


def test_rewrites_bare_class_dunder_name_to_constant():
    before = "def test_x():\n    return tc.get(__class__.__name__)\n"
    after = transform(before, RewriteClassDunderName(class_name="U300_Demo"))
    assert "CLASS_NAME" in after
    assert "__class__.__name__" not in after
    assert "tc.get(CLASS_NAME)" in after


def test_injects_module_level_constant():
    before = "def test_x():\n    return __class__.__name__\n"
    after = transform(before, RewriteClassDunderName(class_name="U300_Demo"))
    assert 'CLASS_NAME = "U300_Demo"' in after


def test_no_injection_when_no_dunder_seen():
    before = "def test_x():\n    return 'no dunder here'\n"
    after = transform(before, RewriteClassDunderName(class_name="U300_Demo"))
    # No rewrite happened → no constant should be injected.
    assert "CLASS_NAME" not in after


def test_no_op_when_class_name_is_none():
    """Defensive: if CaptureClassName didn't see a class (no TestStep in the
    source), we should not crash and should not invent a CLASS_NAME."""
    before = "def test_x():\n    return __class__.__name__\n"
    after = transform(before, RewriteClassDunderName(class_name=None))
    # Without a known class name we can't synthesize the constant, so
    # the rewrite must be skipped. The dunder stays (engineer will see
    # the NameError and ask).
    assert "__class__.__name__" in after
    assert "CLASS_NAME" not in after


def test_handles_multiple_dunder_sites():
    before = (
        "def test_x():\n"
        "    a = tc.get(__class__.__name__, band='n78')\n"
        "    b = tc.get(__class__.__name__, modulation='QPSK')\n"
    )
    after = transform(before, RewriteClassDunderName(class_name="U300_Demo"))
    # Both sites rewritten, constant injected once.
    assert "tc.get(CLASS_NAME, band='n78')" in after
    assert "tc.get(CLASS_NAME, modulation='QPSK')" in after
    assert after.count('CLASS_NAME = "U300_Demo"') == 1


def test_inserts_constant_after_existing_imports():
    before = (
        "import math\n"
        "import time\n"
        "\n"
        "def test_x():\n"
        "    return __class__.__name__\n"
    )
    after = transform(before, RewriteClassDunderName(class_name="U300_Demo"))
    lines = after.splitlines()
    # The constant should appear AFTER both import lines and BEFORE the def.
    const_idx = next(i for i, ln in enumerate(lines) if ln.startswith("CLASS_NAME"))
    def_idx = next(i for i, ln in enumerate(lines) if ln.startswith("def test_x"))
    import_idxs = [i for i, ln in enumerate(lines) if ln.startswith("import ")]
    assert all(idx < const_idx for idx in import_idxs)
    assert const_idx < def_idx


def test_capture_class_name_records_class_name():
    """CaptureClassName is a metadata-only Phase 1 transformer. It must
    record the class name and pass the tree through unchanged."""
    before = (
        "class U300B0_RFEB_EVT_TX_EVM_Power_Sweep:\n"
        "    def Run(self):\n"
        "        pass\n"
    )
    capture = CaptureClassName()
    after = transform(before, capture)
    assert capture.class_name == "U300B0_RFEB_EVT_TX_EVM_Power_Sweep"
    # Tree should be unchanged.
    assert "class U300B0_RFEB_EVT_TX_EVM_Power_Sweep" in after


def test_capture_class_name_stays_none_without_class():
    before = "def some_helper():\n    return 42\n"
    capture = CaptureClassName()
    transform(before, capture)
    assert capture.class_name is None
