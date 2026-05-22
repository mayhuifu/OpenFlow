from textwrap import dedent

from openflow.migrate.transformers import StripLifecycleStubs, transform


def test_strips_trivial_PreRun_PostRun_init():
    before = dedent('''
        class X(Base):
            def __init__(self):
                super().__init__()
            def PreRun(self):
                super().PreRun()
            def PostRun(self):
                super().PostRun()
            def Run(self):
                self.do_work()
    ''')
    after = transform(before, StripLifecycleStubs())
    assert "def __init__" not in after
    assert "def PreRun" not in after
    assert "def PostRun" not in after
    assert "def Run" in after  # Run is preserved


def test_keeps_PreRun_with_real_body():
    before = dedent('''
        class X(Base):
            def PreRun(self):
                super().PreRun()
                self.warmup()
    ''')
    after = transform(before, StripLifecycleStubs())
    assert "def PreRun" in after
    assert "warmup" in after
