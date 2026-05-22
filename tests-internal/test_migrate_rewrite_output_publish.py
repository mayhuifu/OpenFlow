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


def test_recurses_into_for_loop():
    before = dedent('''
        def test_x():
            for i in range(3):
                out_a = i
                results.publish()
    ''')
    after = transform(before, RewriteOutputPublish())
    assert "results.publish(out_a=out_a)" in after


def test_recurses_into_nested_for_loops():
    before = dedent('''
        def test_x():
            for i in range(3):
                for j in range(3):
                    out_a = i
                    out_b = j
                    results.publish()
    ''')
    after = transform(before, RewriteOutputPublish())
    assert "results.publish(out_a=out_a, out_b=out_b)" in after


def test_recurses_into_if_block():
    before = dedent('''
        def test_x():
            if condition:
                out_a = 1
                results.publish()
    ''')
    after = transform(before, RewriteOutputPublish())
    assert "results.publish(out_a=out_a)" in after


def test_outs_assigned_in_nested_block_carry_to_outer_publish():
    before = dedent('''
        def test_x():
            for i in range(3):
                out_a = i
            results.publish()  # outside the loop — out_a still in scope
    ''')
    after = transform(before, RewriteOutputPublish())
    assert "results.publish(out_a=out_a)" in after


def test_nested_function_does_not_pollute_outer_scope():
    before = dedent('''
        def test_x():
            def helper():
                out_x = 1
                return out_x
            results.publish()  # out_x is in helper's scope, not test_x's
    ''')
    after = transform(before, RewriteOutputPublish())
    # `out_x` should NOT be forwarded — it belongs to helper().
    # Check the publish call's argument list only (not any trailing comment).
    publish_call = after.split("results.publish")[1].split(")")[0] + ")"
    assert "out_x" not in publish_call
