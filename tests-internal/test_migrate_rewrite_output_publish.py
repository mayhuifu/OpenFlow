from textwrap import dedent

from openflow.migrate.transformers import RewriteOutputPublish, transform


def test_forwards_single_out_var():
    before = dedent('''
        def test_x():
            out_a = compute_a()
            results.publish()
    ''')
    after = transform(before, RewriteOutputPublish())
    assert "results.publish(out_a=out_a)" in after


def test_forwards_multiple_out_vars_in_order():
    before = dedent('''
        def test_x():
            out_a = 1
            out_b = 2
            out_c = 3
            results.publish()
    ''')
    after = transform(before, RewriteOutputPublish())
    assert "results.publish(out_a=out_a, out_b=out_b, out_c=out_c)" in after


def test_second_publish_accumulates_outs():
    before = dedent('''
        def test_x():
            out_a = 1
            results.publish()
            out_b = 2
            results.publish()
    ''')
    after = transform(before, RewriteOutputPublish())
    lines = [line for line in after.splitlines() if "publish" in line]
    assert "results.publish(out_a=out_a)" in lines[0]
    assert "results.publish(out_a=out_a, out_b=out_b)" in lines[1]


def test_does_not_rewrite_publish_with_existing_args():
    before = dedent('''
        def test_x():
            out_a = 1
            results.publish(gain=10)
    ''')
    after = transform(before, RewriteOutputPublish())
    # Existing call with args is left untouched.
    assert "results.publish(gain=10)" in after
    assert "out_a=out_a" not in after


def test_no_out_vars_leaves_publish_empty():
    before = dedent('''
        def test_x():
            x = 1
            results.publish()
    ''')
    after = transform(before, RewriteOutputPublish())
    # No out_* in scope, so the call stays bare.
    assert "results.publish()" in after


def test_only_outs_above_publish_are_forwarded():
    before = dedent('''
        def test_x():
            out_a = 1
            results.publish()
            out_b = 2  # defined AFTER first publish
    ''')
    after = transform(before, RewriteOutputPublish())
    assert "results.publish(out_a=out_a)" in after
    # out_b should NOT be in the first call.
    publish_call_line = next(line for line in after.splitlines() if "results.publish" in line)
    assert "out_b" not in publish_call_line
