"""Tests for the R&S SMW200A signal generator SCPI driver."""
from openflow.instruments.sg_rs_smw200a import RsSmw200a


def test_idn_in_emulation_contains_smw200a():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    idn = sg.identify()
    assert "SMW200A" in idn
    assert "Rohde" in idn
    sg.close()


def test_set_frequency_emits_source_frequency():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.set_frequency(2.45e9)
    log = "\n".join(sg._scpi_log)
    assert "SOURce:FREQuency" in log
    sg.close()


def test_set_rf_power_emits_source_power_with_value():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.set_rf_power(-30.0)
    log = "\n".join(sg._scpi_log)
    assert "SOURce:POWer" in log
    assert "-30" in log
    sg.close()


def test_output_on_emits_output_state_on():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.output_on()
    assert "OUTPut:STATe ON" in sg._scpi_log
    sg.close()


def test_output_off_emits_output_state_off():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.output_off()
    assert "OUTPut:STATe OFF" in sg._scpi_log
    sg.close()


def test_set_modulation_state_on():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.set_modulation_state(True)
    assert "SOURce:MODulation:STATe ON" in sg._scpi_log
    sg.close()


def test_set_modulation_state_off():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.set_modulation_state(False)
    assert "SOURce:MODulation:STATe OFF" in sg._scpi_log
    sg.close()


def test_set_arb_state_on():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.set_arb_state(True)
    assert "SOURce:BB:ARBitrary:STATe ON" in sg._scpi_log
    sg.close()


def test_load_arb_waveform_quotes_name():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.load_arb_waveform("my_5g_qpsk.arb")
    log = "\n".join(sg._scpi_log)
    assert "ARBitrary:WAVeform:SELect" in log
    assert '"my_5g_qpsk.arb"' in log
    sg.close()


def test_set_arb_signal_rf_writes_freq_power_and_output():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    sg.set_arb_signal_rf(frequency_Hz=2.5e9, power_dBm=-10.0, modulation="QPSK")
    log = "\n".join(sg._scpi_log)
    assert "SOURce:FREQuency" in log
    assert "SOURce:POWer" in log
    assert "OUTPut:STATe ON" in log
    sg.close()


def test_drain_errors_works():
    sg = RsSmw200a(resource="MOCK::", is_emulation=True)
    sg.open()
    assert sg.drain_errors() == []
    sg.close()
