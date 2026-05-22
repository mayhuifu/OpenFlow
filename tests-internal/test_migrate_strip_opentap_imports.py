"""Tests for StripOpenTapImports + the transform() helper."""
from textwrap import dedent

from openflow.migrate.transformers import StripOpenTapImports, transform


def _norm(s: str) -> str:
    """Strip blank lines for comparison."""
    return "\n".join(line for line in s.splitlines() if line.strip())


def test_strips_from_opentap_import_star():
    before = "from opentap import *\nimport numpy as np\n"
    after = transform(before, StripOpenTapImports())
    assert _norm(after) == _norm("import numpy as np\n")


def test_strips_import_OpenTap():
    before = dedent("""
        import OpenTap
        import sys
    """)
    after = transform(before, StripOpenTapImports())
    assert "OpenTap" not in after
    assert "import sys" in after


def test_strips_clr_imports_and_AddReferences():
    before = dedent("""
        import clr
        clr.AddReference("System.Collections")
        clr.AddReference("OpenTap.Plugins.BasicSteps")
        from System.Collections.Generic import List
        from System import Int32, Double, String, Int64
        import numpy as np
    """)
    after = transform(before, StripOpenTapImports())
    assert "clr" not in after
    assert "System" not in after
    assert "import numpy as np" in after


def test_preserves_unrelated_imports():
    before = dedent("""
        import re
        import math
        import time
        from opentap import *
    """)
    after = transform(before, StripOpenTapImports())
    assert "import re" in after
    assert "import math" in after
    assert "import time" in after
    assert "opentap" not in after
