"""Tests for the spectrum-analyzer drivers — base + Keysight + R&S."""
import pytest

from openflow.instruments.sa_base import SpectrumAnalyzerBase
from openflow.instruments.sa_keysight_n9020b import KeysightN9020B
from openflow.instruments.sa_rs_fsw import RsFsw


@pytest.fixture(params=[KeysightN9020B, RsFsw], ids=["keysight_n9020b", "rs_fsw"])
def sa_class(request):
    return request.param


def test_subclasses_are_spectrum_analyzer_base():
    assert issubclass(KeysightN9020B, SpectrumAnalyzerBase)
    assert issubclass(RsFsw, SpectrumAnalyzerBase)


def test_idn_distinguishes_vendors():
    k = KeysightN9020B(resource="MOCK::", is_emulation=True)
    r = RsFsw(resource="MOCK::", is_emulation=True)
    k.open()
    r.open()
    assert "Keysight" in k.identify()
    assert "N9020B" in k.identify()
    assert "Rohde" in r.identify()
    assert "FSW" in r.identify()
    k.close()
    r.close()


def test_set_center_frequency(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    sa.set_center_frequency(2.5e9)
    log = "\n".join(sa._scpi_log)
    assert "SENSe:FREQuency:CENTer" in log
    sa.close()


def test_set_span(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    sa.set_span(20e6)
    log = "\n".join(sa._scpi_log)
    assert "SENSe:FREQuency:SPAN" in log
    sa.close()


def test_set_resolution_bw(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    sa.set_resolution_bw(100e3)
    log = "\n".join(sa._scpi_log)
    assert "SENSe:BANDwidth:RESolution" in log
    sa.close()


def test_set_video_bw(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    sa.set_video_bw(30e3)
    log = "\n".join(sa._scpi_log)
    assert "SENSe:BANDwidth:VIDeo" in log
    sa.close()


def test_set_reference_level(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    sa.set_reference_level(-10.0)
    log = "\n".join(sa._scpi_log)
    assert "DISPlay:WINDow:TRACe:Y:RLEVel" in log
    assert "-10" in log
    sa.close()


def test_trigger_sweep_writes_init_immediate_and_waits_opc(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    sa.trigger_sweep()
    log = "\n".join(sa._scpi_log)
    assert "INITiate:IMMediate" in log
    assert "*OPC?" in log
    sa.close()


def test_meas_marker_peak_returns_tuple_in_emulation(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    freq, power = sa.meas_marker_peak()
    assert isinstance(freq, float)
    assert isinstance(power, float)
    # Canned values from the base class — sanity-check finite range.
    assert 1e6 < freq < 100e9
    assert -100 < power < 30
    sa.close()


def test_meas_channel_power_returns_float_in_emulation(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    p = sa.meas_channel_power(channel_bw_Hz=20e6)
    assert isinstance(p, float)
    sa.close()


def test_drain_errors_in_emulation_clean(sa_class):
    sa = sa_class(resource="MOCK::", is_emulation=True)
    sa.open()
    assert sa.drain_errors() == []
    sa.close()
