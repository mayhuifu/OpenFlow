"""Tests for the RewriteConfigNames transformer.

This transformer runs AFTER RewriteInputAttrs, so by the time it sees
the tree the OpenTAP input names already look like ``config.<old_name>``.
Its job is the last-mile rename of the three OpenTAP-Python file-path
inputs to their new OpenFlowConfig field names:

    config.conditions_limits_config  -> config.limits_path
    config.deembedding_config        -> config.deembedding_path
    config.calibration_file_config   -> config.calibration_path
"""
from openflow.migrate.transformers import RewriteConfigNames, transform


def test_rewrites_conditions_limits_config():
    before = "tc = Testconditions_Limits(config.conditions_limits_config)\n"
    after = transform(before, RewriteConfigNames())
    assert "config.limits_path" in after
    assert "conditions_limits_config" not in after


def test_rewrites_deembedding_config():
    before = "d = Deembedding(config.deembedding_config)\n"
    after = transform(before, RewriteConfigNames())
    assert "config.deembedding_path" in after
    assert "deembedding_config" not in after


def test_rewrites_calibration_file_config():
    before = "cal = Calibration_File(config.calibration_file_config, a, b)\n"
    after = transform(before, RewriteConfigNames())
    assert "config.calibration_path" in after
    assert "calibration_file_config" not in after


def test_leaves_unmapped_config_attrs_alone():
    before = "x = config.band\ny = config.rfbw_Hz\n"
    after = transform(before, RewriteConfigNames())
    assert "config.band" in after
    assert "config.rfbw_Hz" in after


def test_leaves_other_objects_attr_alone():
    # `something.deembedding_config` (not `config.<X>`) must not be rewritten.
    before = "x = obj.deembedding_config\ny = self.calibration_file_config\n"
    after = transform(before, RewriteConfigNames())
    assert "obj.deembedding_config" in after
    assert "self.calibration_file_config" in after
    assert "deembedding_path" not in after
    assert "calibration_path" not in after


def test_rewrites_inside_nested_call_arg():
    # The real OpenTAP source nests these inside multi-arg constructors.
    before = (
        "tc, d, cal = ("
        "Testconditions_Limits(config.conditions_limits_config),"
        " Deembedding(config.deembedding_config),"
        " Calibration_File(config.calibration_file_config, x, y))\n"
    )
    after = transform(before, RewriteConfigNames())
    assert "Testconditions_Limits(config.limits_path)" in after
    assert "Deembedding(config.deembedding_path)" in after
    assert "Calibration_File(config.calibration_path, x, y)" in after


def test_idempotent_on_already_renamed():
    before = "tc = Testconditions_Limits(config.limits_path)\n"
    after = transform(before, RewriteConfigNames())
    assert after == before
