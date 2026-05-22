from textwrap import dedent

from openflow.migrate.transformers import ExtractTestcaseId, transform


def test_lifts_testcase_id_to_module_level():
    before = dedent('''
        class X(Base):
            Testcase_ID = property(String, "U300B0-RFE-EVT-005") \\
                .add_attribute(OpenTap.Display("Testcase_ID", "Testcase Identifier"))
            def Run(self):
                pass
    ''')
    after = transform(before, ExtractTestcaseId())
    assert 'TESTCASE_ID = "U300B0-RFE-EVT-005"' in after
    assert "Testcase_ID =" not in after


def test_no_testcase_id_in_class_is_noop():
    before = "class Y: pass\n"
    after = transform(before, ExtractTestcaseId())
    assert "class Y" in after
    assert "TESTCASE_ID" not in after
