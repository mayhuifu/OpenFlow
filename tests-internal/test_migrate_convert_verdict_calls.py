from openflow.migrate.transformers import ConvertVerdictCalls, transform


def test_pass_verdict_becomes_noop():
    before = "self.UpgradeVerdict(OpenTap.Verdict.Pass)\n"
    after = transform(before, ConvertVerdictCalls())
    assert "UpgradeVerdict" not in after
    assert "pass" in after


def test_fail_verdict_becomes_assert_false():
    before = "self.UpgradeVerdict(OpenTap.Verdict.Fail)\n"
    after = transform(before, ConvertVerdictCalls())
    assert "UpgradeVerdict" not in after
    assert "assert False" in after


def test_post_self_strip_form_also_handled():
    before = "UpgradeVerdict(OpenTap.Verdict.Fail)\n"
    after = transform(before, ConvertVerdictCalls())
    assert "assert False" in after
