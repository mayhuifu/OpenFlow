from textwrap import dedent

from openflow.migrate.transformers import RewriteInputAttrs, transform


def test_rewrites_bare_in_name_to_config_attr():
    before = "x = in_band\n"
    after = transform(before, RewriteInputAttrs())
    assert "config.band" in after
    assert "in_band" not in after


def test_strips_in_prefix():
    before = "freq = in_dl_freq_pll_Hz\n"
    after = transform(before, RewriteInputAttrs())
    assert "config.dl_freq_pll_Hz" in after


def test_does_not_rewrite_assignment_target():
    before = "in_band = 'n78'\n"
    after = transform(before, RewriteInputAttrs())
    # Assignment to in_band stays — it's defining a local, not reading an input.
    assert "in_band = 'n78'" in after
    assert "config.band" not in after


def test_rewrites_inside_call_arg():
    before = "result = setup(band=in_band, bw=in_rfbw_Hz)\n"
    after = transform(before, RewriteInputAttrs())
    assert "band=config.band" in after
    assert "bw=config.rfbw_Hz" in after


def test_leaves_non_in_names_alone():
    before = "x = some_var\ny = another_thing\n"
    after = transform(before, RewriteInputAttrs())
    assert "some_var" in after
    assert "another_thing" in after


def test_skips_when_in_name_is_locally_defined_in_function():
    # If the function defines `in_band` as a local, we shouldn't rewrite reads of it.
    # NOTE: comment text deliberately avoids the literal token we're asserting
    # absence of, so the assertion reflects transformer behavior, not comment text.
    before = '''
def test_x():
    in_band = "n78"  # local binding, not inherited
    return in_band   # should stay as a local read
'''
    after = transform(before, RewriteInputAttrs())
    assert "config.band" not in after
    assert "return in_band" in after
