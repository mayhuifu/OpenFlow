from openflow.migrate.transformers import RewriteBoardSerials, transform


def test_rewrites_RFEB_SN_to_config_rfeb_sn():
    before = "x = RFEB_SN\n"
    after = transform(before, RewriteBoardSerials())
    assert "config.rfeb_sn" in after
    assert "RFEB_SN" not in after


def test_rewrites_RFHB_SN_to_config_rfhb_sn():
    before = "x = RFHB_SN\n"
    after = transform(before, RewriteBoardSerials())
    assert "config.rfhb_sn" in after
    assert "RFHB_SN" not in after


def test_does_not_rewrite_assignment_target():
    before = "RFEB_SN = 'ABC123'\n"
    after = transform(before, RewriteBoardSerials())
    # Assignment to RFEB_SN stays — it's defining a local.
    assert "RFEB_SN = 'ABC123'" in after
    assert "config.rfeb_sn" not in after


def test_rewrites_inside_call_arg():
    before = "x = build(serial=RFEB_SN, hb=RFHB_SN)\n"
    after = transform(before, RewriteBoardSerials())
    assert "serial=config.rfeb_sn" in after
    assert "hb=config.rfhb_sn" in after


def test_leaves_other_uppercase_names_alone():
    before = "x = SOME_CONST\ny = TESTCASE_ID\n"
    after = transform(before, RewriteBoardSerials())
    assert "SOME_CONST" in after
    assert "TESTCASE_ID" in after  # module-level constants stay
