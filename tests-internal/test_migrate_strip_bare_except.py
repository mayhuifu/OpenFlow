from textwrap import dedent

from openflow.migrate.transformers import StripBareExcept, transform


def test_rewrites_bare_except_to_Exception():
    before = dedent("""
        try:
            do_thing()
        except:
            handle_it()
    """)
    after = transform(before, StripBareExcept())
    assert "except:" not in after
    assert "except Exception:" in after


def test_leaves_typed_except_alone():
    before = dedent("""
        try:
            do_thing()
        except ValueError:
            handle_it()
    """)
    after = transform(before, StripBareExcept())
    assert "except ValueError:" in after


def test_handles_multiple_bare_excepts():
    before = dedent("""
        try:
            do_a()
        except:
            pass
        try:
            do_b()
        except:
            pass
    """)
    after = transform(before, StripBareExcept())
    assert after.count("except Exception:") == 2
    assert "except:" not in after
