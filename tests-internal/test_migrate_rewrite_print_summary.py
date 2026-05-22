"""Tests for the RewritePrintSummary transformer.

V2: rewrite bare-name ``Print_Summary(...)`` calls (left over from
ConvertClassToTestFunction stripping ``self.``) into ``logger.info(...)``
calls preserving the keyword arguments. AddLoggingHeader already
guarantees a ``logger`` is in scope.

Behavior:

  Print_Summary()                         -> logger.info("Print_Summary")
  Print_Summary(modulation='QPSK')        -> logger.info("Print_Summary: modulation=%s", 'QPSK')
  Print_Summary(m='QPSK', power=10)       -> logger.info("Print_Summary: m=%s power=%s", 'QPSK', 10)

Bare-name only — ``obj.Print_Summary()`` is left alone (could be a
method on a different object).
"""
from openflow.migrate.transformers import RewritePrintSummary, transform


def test_rewrites_print_summary_to_logger_info():
    before = "def test_x():\n    Print_Summary()\n"
    after = transform(before, RewritePrintSummary())
    assert "Print_Summary(" not in after  # call form is gone
    assert "logger.info" in after


def test_preserves_keyword_args_as_format_args():
    before = "def test_x():\n    Print_Summary(modulation='QPSK')\n"
    after = transform(before, RewritePrintSummary())
    assert "Print_Summary(" not in after  # call form is gone
    assert "logger.info" in after
    # The value should still appear in the rewritten call.
    assert "'QPSK'" in after
    # The kwarg name should appear in the format string.
    assert "modulation" in after


def test_preserves_multiple_keyword_args():
    before = "def test_x():\n    Print_Summary(m='QPSK', power=10)\n"
    after = transform(before, RewritePrintSummary())
    assert "logger.info" in after
    assert "'QPSK'" in after
    assert "10" in after
    assert "m" in after
    assert "power" in after


def test_leaves_attribute_call_alone():
    before = "def test_x(obj):\n    obj.Print_Summary()\n"
    after = transform(before, RewritePrintSummary())
    assert "obj.Print_Summary()" in after


def test_leaves_unrelated_calls_alone():
    before = "def test_x():\n    other_func(x=1)\n"
    after = transform(before, RewritePrintSummary())
    assert "other_func(x=1)" in after


def test_handles_multiple_print_summary_calls():
    before = (
        "def test_x():\n"
        "    Print_Summary(m='QPSK')\n"
        "    Print_Summary(m='16QAM')\n"
    )
    after = transform(before, RewritePrintSummary())
    assert "Print_Summary(" not in after  # call form is gone
    assert after.count("logger.info") == 2
