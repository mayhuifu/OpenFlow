from textwrap import dedent

from openflow.migrate.transformers import RewriteImportPaths, transform


def test_rewrites_UMT_Instruments_CMW100_import():
    before = "from UMT_Instruments.CMW100 import CMW100\n"
    after = transform(before, RewriteImportPaths())
    assert "from openflow.instruments.cmw100 import CMW100" in after
    assert "UMT_Instruments" not in after


def test_rewrites_U300_RFEngine_Deembedding_import():
    before = "from U300_RFEngine.Deembedding import Deembedding\n"
    after = transform(before, RewriteImportPaths())
    assert "from openflow.rfengine.deembedding import Deembedding" in after


def test_rewrites_UMT_DUTs_UMT_DUT_import():
    before = "from UMT_DUTs.UMT_DUT import UMT_DUT\n"
    after = transform(before, RewriteImportPaths())
    assert "from openflow.dut.base import Dut" in after


def test_drops_U300_RFEngine_EVT_Base_import():
    before = dedent("""
        from .U300_RFEngine_EVT_Base import U300_RFEngine_EVT_Base
        from U300_RFEngine.U300_RFEngine_EVT_Base import U300_RFEngine_EVT_Base
    """)
    after = transform(before, RewriteImportPaths())
    assert "U300_RFEngine_EVT_Base" not in after


def test_drops_UMT_Base_UMT_TestCase_import():
    before = "from UMT_Base.UMT_TestCase import UMT_TestCase\n"
    after = transform(before, RewriteImportPaths())
    assert "UMT_TestCase" not in after


def test_leaves_numpy_re_time_imports_intact():
    before = dedent("""
        import numpy as np
        import re
        import time
        import math
    """)
    after = transform(before, RewriteImportPaths())
    assert "import numpy as np" in after
    assert "import re" in after
    assert "import time" in after
    assert "import math" in after
