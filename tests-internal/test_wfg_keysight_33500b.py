"""Tests for the Keysight 33500B waveform generator SCPI driver."""
import pytest

from openflow.instruments.wfg_keysight_33500b import Keysight33500B


def test_idn_in_emulation_mentions_keysight():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    idn = wfg.identify()
    assert "Keysight" in idn
    assert "33522B" in idn or "33500" in idn
    wfg.close()


def test_load_arb_file_emits_data_arbitrary_load():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.load_arb_file("/path/to/wave.arb", sample_rate_Hz=2e6, name="MYARB")
    log = "\n".join(wfg._scpi_log)
    assert "DATA:ARBitrary:LOAD" in log
    assert '"/path/to/wave.arb"' in log
    assert "FUNCtion:ARBitrary:SRATe" in log
    assert "FUNCtion ARB" in log
    wfg.close()


def test_set_arb_sample_rate_emits_srate():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.set_arb_sample_rate(5e6)
    log = "\n".join(wfg._scpi_log)
    assert "FUNCtion:ARBitrary:SRATe" in log
    wfg.close()


def test_set_arb_output_amplitude_Vpp_emits_voltage():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.set_arb_output_amplitude_Vpp(1.5)
    log = "\n".join(wfg._scpi_log)
    assert "VOLTage" in log
    assert "1.5" in log
    wfg.close()


def test_output_on_channel_1_emits_source1_output_on():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.output_on(channel=1)
    assert any("SOURce1:OUTPut ON" in s for s in wfg._scpi_log)
    wfg.close()


def test_output_on_channel_2_emits_source2_output_on():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.output_on(channel=2)
    assert any("SOURce2:OUTPut ON" in s for s in wfg._scpi_log)
    wfg.close()


def test_output_off_emits_output_off():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.output_off()
    assert any("OUTPut OFF" in s for s in wfg._scpi_log)
    wfg.close()


def test_set_sync_mode_ext_emits_trigger_source_ext():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.set_sync_mode(ext=True)
    assert any("TRIGger:SOURce EXT" in s for s in wfg._scpi_log)
    wfg.close()


def test_set_sync_mode_internal_emits_trigger_source_imm():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    wfg.set_sync_mode(ext=False)
    assert any("TRIGger:SOURce IMM" in s for s in wfg._scpi_log)
    wfg.close()


def test_invalid_channel_raises():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    with pytest.raises(ValueError, match="channel"):
        wfg.output_on(channel=3)
    wfg.close()


def test_drain_errors_in_emulation_clean():
    wfg = Keysight33500B(resource="MOCK::", is_emulation=True)
    wfg.open()
    assert wfg.drain_errors() == []
    wfg.close()
