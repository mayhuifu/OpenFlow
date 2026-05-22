from textwrap import dedent

from openflow.migrate.transformers import StripAttributeDecorators, transform


def test_strips_display_decorator():
    before = dedent('''
        @attribute(OpenTap.Display("X", "desc", "group"))
        @attribute(OpenTap.AllowAnyChild())
        class X(Base):
            pass
    ''')
    after = transform(before, StripAttributeDecorators())
    assert "@attribute" not in after
    assert "class X(Base):" in after


def test_keeps_non_attribute_decorators():
    before = dedent('''
        @pytest.fixture
        @attribute(OpenTap.Display("X", "d", "g"))
        def f():
            pass
    ''')
    after = transform(before, StripAttributeDecorators())
    assert "@pytest.fixture" in after
    assert "@attribute" not in after
