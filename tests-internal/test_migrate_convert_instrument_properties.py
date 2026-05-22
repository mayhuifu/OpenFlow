from textwrap import dedent

from openflow.migrate.transformers import ConvertInstrumentProperties, transform


def test_records_and_strips_instrument_property():
    before = dedent('''
        class X(Base):
            cmw100 = property(CMW100, None).add_attribute(OpenTap.Display("CMW100", "d", "Instruments"))
            wfg = property(WFG, None).add_attribute(OpenTap.Display("WFG", "d", "Instruments"))
            dut = property(UMT_DUT, None).add_attribute(OpenTap.Display("DUT", "d", "DUT"))
            def Run(self):
                self.cmw100.do_something()
    ''')
    transformer = ConvertInstrumentProperties()
    after = transform(before, transformer)
    assert "cmw100 = property" not in after
    assert "wfg = property" not in after
    assert "dut = property" not in after
    assert transformer.instrument_names == ["cmw100", "wfg", "dut"]
