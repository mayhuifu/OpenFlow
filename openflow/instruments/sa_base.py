"""Cross-vendor spectrum-analyzer base class.

The Keysight N9020B MXA and R&S FSW share ~80% of their SCPI surface.
This base owns the shared commands; concrete subclasses
(``KeysightN9020B``, ``RsFsw``) override only what differs.

API surface (consumed by migrated EVT tests + future RX sensitivity work):

    set_center_frequency(freq_Hz)
    set_span(span_Hz)
    set_resolution_bw(rbw_Hz)
    set_video_bw(vbw_Hz)
    set_reference_level(level_dBm)
    trigger_sweep()
    meas_marker_peak() -> (freq_Hz, power_dBm)
    meas_channel_power(channel_bw_Hz) -> power_dBm
"""
from __future__ import annotations

from openflow.instruments.scpi import SCPIInstrument

# Emulated peak — a typical "OK we got a signal" pair.
_EMULATION_PEAK_FREQ_HZ = 2.5e9
_EMULATION_PEAK_POWER_DBM = -20.0
_EMULATION_CHANNEL_POWER_DBM = -25.0


class SpectrumAnalyzerBase(SCPIInstrument):
    """Cross-vendor SCPI surface for spectrum analyzers.

    Concrete subclasses override ``_IDN_HINT`` and (where SCPI differs)
    individual methods. The defaults here use commands that both
    Keysight (N9020B family) and R&S (FSW family) speak.
    """

    _IDN_HINT = "GenericSA,EMU0,A.00.00-EMU"

    def set_center_frequency(self, freq_Hz: float) -> None:
        self.write(f"SENSe:FREQuency:CENTer {freq_Hz:g}")

    def set_span(self, span_Hz: float) -> None:
        self.write(f"SENSe:FREQuency:SPAN {span_Hz:g}")

    def set_resolution_bw(self, rbw_Hz: float) -> None:
        self.write(f"SENSe:BANDwidth:RESolution {rbw_Hz:g}")

    def set_video_bw(self, vbw_Hz: float) -> None:
        self.write(f"SENSe:BANDwidth:VIDeo {vbw_Hz:g}")

    def set_reference_level(self, level_dBm: float) -> None:
        self.write(f"DISPlay:WINDow:TRACe:Y:RLEVel {level_dBm:g}")

    def trigger_sweep(self) -> None:
        """Trigger a single sweep and block until done (uses *OPC?)."""
        self.write("INITiate:CONTinuous OFF")
        self.write("INITiate:IMMediate")
        # *OPC? blocks until the sweep finishes.
        self.query("*OPC?")

    def meas_marker_peak(self) -> tuple[float, float]:
        """Place a marker on the peak and return (freq_Hz, power_dBm).

        Standard SCPI: place marker 1 on max trace point, then query
        X/Y values.
        """
        self.write("CALCulate:MARKer1:MAXimum")
        freq_str = self.query("CALCulate:MARKer1:X?")
        power_str = self.query("CALCulate:MARKer1:Y?")
        return float(freq_str), float(power_str)

    def meas_channel_power(self, channel_bw_Hz: float) -> float:
        """Configure a channel-power measurement and return the result."""
        self.write("CALCulate:MARKer:FUNCtion:POWer:STATe ON")
        self.write("CALCulate:MARKer:FUNCtion:POWer:SELect CHPower")
        self.write(f"SENSe:POWer:ACHannel:BANDwidth:INTegration {channel_bw_Hz:g}")
        result = self.query("CALCulate:MARKer:FUNCtion:POWer:RESult? CHPower")
        return float(result)

    # --- Emulation overrides ----------------------------------------------
    def _emulated_response(self, scpi: str) -> str:
        if scpi == "*OPC?":
            return "1"
        if scpi == "CALCulate:MARKer1:X?":
            return f"{_EMULATION_PEAK_FREQ_HZ:.6E}"
        if scpi == "CALCulate:MARKer1:Y?":
            return f"{_EMULATION_PEAK_POWER_DBM:.6E}"
        if scpi == "CALCulate:MARKer:FUNCtion:POWer:RESult? CHPower":
            return f"{_EMULATION_CHANNEL_POWER_DBM:.6E}"
        return super()._emulated_response(scpi)
