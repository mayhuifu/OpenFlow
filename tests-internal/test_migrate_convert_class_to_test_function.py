from textwrap import dedent

from openflow.migrate.transformers import ConvertClassToTestFunction, transform


def test_class_with_Run_becomes_test_function():
    before = dedent('''
        class U300B0_RFEB_EVT_TX_EVM_Power_Sweep(U300_RFEngine_EVT_Base):
            def __init__(self):
                super().__init__()
            def PreRun(self):
                super().PreRun()
            def PostRun(self):
                super().PostRun()
            def Run(self):
                super().Run()
                self.do_thing()
    ''')
    transformer = ConvertClassToTestFunction(instrument_fixtures=["cmw100", "dut"])
    after = transform(before, transformer)
    assert "class U300B0_RFEB_EVT_TX_EVM_Power_Sweep" not in after
    assert "def test_u300b0_rfeb_evt_tx_evm_power_sweep(cmw100, dut, config, results):" in after
    assert "self.do_thing()" not in after
    assert "do_thing()" in after  # self. stripped


def test_self_prefix_is_stripped_from_method_calls_and_attrs():
    before = dedent('''
        class X(Base):
            def Run(self):
                self.cmw100.write("X")
                v = self.in_band
    ''')
    transformer = ConvertClassToTestFunction(instrument_fixtures=["cmw100"])
    after = transform(before, transformer)
    assert "self." not in after
    assert "cmw100.write" in after
    assert "in_band" in after
