from textwrap import dedent

from openflow.migrate.transformers import ConvertInputProperties, transform


def test_records_and_strips_input_property():
    before = dedent('''
        class X(Base):
            in_rx_power_backoff_dB = property(Double, 10.0).add_attribute(OpenTap.Display(...))
            in_band = property(String, "n78").add_attribute(OpenTap.Display(...))
            def Run(self):
                pass
    ''')
    transformer = ConvertInputProperties()
    after = transform(before, transformer)
    assert "in_rx_power_backoff_dB =" not in after
    assert "in_band =" not in after
    assert transformer.inputs == [("in_rx_power_backoff_dB", "10.0"),
                                  ("in_band", '"n78"')]
