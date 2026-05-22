"""R&S SMW200A vector signal generator SCPI driver.

The SMW200A is the reference RF signal generator for U300 bench setups —
supports 5G NR + LTE vector modulation natively. Pure-SCPI driver (no R&S
vendor SDK dependency), so this same surface works against the SMW100A or
older R&S vector SG models with minor SCPI tweaks.

API surface (consumed by the migrated EVT tests):

    set_frequency(freq_Hz)               -> SOURce:FREQuency
    set_rf_power(power_in_dBm)           -> SOURce:POWer
    output_on() / output_off()           -> OUTPut:STATe ON|OFF
    set_modulation_state(on)             -> SOURce:MODulation:STATe ON|OFF
    set_arb_signal_rf(freq, power, modulation)
        ^ V1-compatible composite — drives frequency + power + ARB on
"""
from __future__ import annotations

from openflow.instruments.scpi import SCPIInstrument


class RsSmw200a(SCPIInstrument):
    """R&S SMW200A vector signal generator."""

    _IDN_HINT = "Rohde&Schwarz,SMW200A,1412.0000K02/EMU0,1.00.00-EMU"

    # --- Frequency / power ------------------------------------------------
    def set_frequency(self, freq_Hz: float) -> None:
        """Set the carrier frequency."""
        self.write(f"SOURce:FREQuency {freq_Hz:g}")

    def set_rf_power(self, power_in_dBm: float) -> None:
        """Set the RF output power."""
        self.write(f"SOURce:POWer {power_in_dBm:g}")

    # --- Output control ---------------------------------------------------
    def output_on(self) -> None:
        """Turn the RF output on."""
        self.write("OUTPut:STATe ON")

    def output_off(self) -> None:
        """Turn the RF output off."""
        self.write("OUTPut:STATe OFF")

    # --- Modulation control -----------------------------------------------
    def set_modulation_state(self, on: bool) -> None:
        """Enable or disable the modulation source."""
        self.write(f"SOURce:MODulation:STATe {'ON' if on else 'OFF'}")

    # --- ARB (Arbitrary Waveform) control ---------------------------------
    def set_arb_state(self, on: bool) -> None:
        """Enable or disable the ARB generator."""
        self.write(f"SOURce:BB:ARBitrary:STATe {'ON' if on else 'OFF'}")

    def load_arb_waveform(self, waveform_name: str) -> None:
        """Load an ARB waveform from the SMW200A's internal storage."""
        self.write(f'SOURce:BB:ARBitrary:WAVeform:SELect "{waveform_name}"')

    # --- V1-style composite call ------------------------------------------
    def set_arb_signal_rf(self, *, frequency_Hz: float, power_dBm: float,
                          modulation: str = "QPSK", **_extra: object) -> None:
        """Set frequency + power + enable RF output. Composite call that
        mirrors the CMW100 generator surface so the migrated EVT tests
        can drive an SG or the CMW100's internal generator identically.

        The ``modulation`` argument is currently accepted but only logged —
        actual modulation loading uses ``load_arb_waveform()`` with a
        bench-prepared waveform file. Engineer wires the right ARB
        waveform name in their test.
        """
        self.log.info("RsSmw200a.set_arb_signal_rf: freq=%g Hz, power=%g dBm, "
                      "modulation=%s", frequency_Hz, power_dBm, modulation)
        self.set_frequency(frequency_Hz)
        self.set_rf_power(power_dBm)
        self.output_on()
