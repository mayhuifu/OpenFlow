from textwrap import dedent

from openflow.migrate.transformers import AddLoggingHeader, transform


def test_adds_header_when_logger_calls_present():
    before = dedent("""
        import numpy as np

        def test_x():
            logger.info("hello")
    """)
    after = transform(before, AddLoggingHeader())
    assert "import logging" in after
    assert "logger = logging.getLogger(__name__)" in after


def test_no_op_when_no_logger_calls():
    before = dedent("""
        import numpy as np

        def test_x():
            print("hi")
    """)
    after = transform(before, AddLoggingHeader())
    assert "import logging" not in after
    assert "getLogger" not in after


def test_no_op_when_logger_already_defined():
    before = dedent("""
        import logging
        logger = logging.getLogger(__name__)

        def test_x():
            logger.info("hi")
    """)
    after = transform(before, AddLoggingHeader())
    # No duplicate import or assignment introduced.
    assert after.count("import logging") == 1
    assert after.count("logger = logging.getLogger") == 1


def test_inserts_after_existing_imports():
    before = dedent("""
        import numpy as np
        import re

        def test_x():
            logger.warning("ok")
    """)
    after = transform(before, AddLoggingHeader())
    # The new import should land near the top, not inside the function.
    lines = after.splitlines()
    import_logging_idx = next(i for i, line in enumerate(lines) if "import logging" in line)
    def_idx = next(i for i, line in enumerate(lines) if "def test_x" in line)
    assert import_logging_idx < def_idx
