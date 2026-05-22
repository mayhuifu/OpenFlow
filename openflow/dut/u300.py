"""DUT_U300 — U300 RFIC + RFEB driver.

Ported from UMT_DUTs/DUT_U300.py minus OpenTAP scaffolding. V1b ports only the
methods exercised by U300B0_RFEB_EVT_TX_EVM_Power_Sweep (cmd_initialize,
set_rfTxPower, set_arb_signal_bb, set_arb_power_dBFSrms, get_BandNumber,
dBm2dBV, set_rfTxStop) plus their internal dependencies. Other methods
(Rx ops, MIPI, calibration, aux ADC, FFT, temperature sensors) fall through
to Dut.__getattr__ which raises NotImplementedError pointing engineers at the
specific method that needs porting.
"""
from __future__ import annotations

import logging

import numpy as np

from openflow.dut.base import Dut
from openflow.instruments.stubs import WFG


class DUT_U300(Dut):
    """U300 RFIC + RFEB driver.

    Ported subset; methods outside the TX EVM measurement path fall through to
    Dut.__getattr__ which raises NotImplementedError.
    """

    # ====== RFD Version selection ======= #
    # Original used OpenTAP property() declarations; here they are plain class
    # attributes with type annotations (per V1b transformation pattern).
    board_type: str = "u300_a1_rfeb1p1"
    atcmd_log_bool: bool = False
    has_arb_wfg: bool = False

    def __init__(self) -> None:
        super().__init__()  # The base class initializer must be invoked.
        self.log = logging.getLogger(__name__)
        self.Name = "DUT_U300"
        self.reg_cached = None
        self.reg_read = None
        Vcal1 = 0.3
        Ccal1 = 384
        Vcal2 = 0.7
        Ccal2 = 896
        self.aux_cal_a0 = (Vcal1 * Ccal2 - Vcal2 * Ccal1) / (Ccal2 - Ccal1)
        self.aux_cal_a1 = (Vcal2 - Vcal1) / (Ccal2 - Ccal1)
        self.aux_temp_a0 = np.log10(280) * 25 / 0.447
        self.aux_temp_a1 = -25 / 0.447
        self.w_aux_addr_mask = 0x2000
        self.aux_cal_temp_int_otpt = 740    # 638
        self.aux_cal_temp_int_rt = 23  # room temperature 25C
        self.system_image_version = None
        self.reg_map = None

    def Open(self) -> None:
        # super().Open()
        pass

    def Close(self) -> None:
        # super().Close()
        pass

    # # ==================== U300 related functions ======================== # #

    def load_reg_map(self):
        """Load register map."""
        # Source body: self.log.Error("Function not implemented") — kept as a warning
        # since this is not in the TX-EVM path's hot path. cmd_initialize calls a
        # different reg-map loader (the U300RegisterMap import block).
        self.log.warning("load_reg_map: not implemented in V1b port")

    def save_reg_map(self, filename):
        """Saves all read values to a .csv file."""
        self.log.warning("save_reg_map: not implemented in V1b port")

    # ========================================RFD Specific Functions=====================================
    def cmd_initialize(
        self,
        pmic_startup: bool = True,
        rfic_startup: bool = True,
        reboot_enable: bool = False,
        force_reboot=None,
    ):
        """Initialize DUT: RFEB1 + RFHB.

        In V1b emulation mode, this is a no-op (the source's body relied on the
        rfd_simulator register-map import, which is OpenTAP-specific and not
        bundled into V1b).

        V1f audit: on the real-hardware path this now raises
        ``NotImplementedError`` rather than silently warning-and-returning.
        The source-level body performs the RFEB1 + RFHB init sequence via
        ``rfd_simulator`` register writes; without that port wired up the
        only safe behavior is to fail loudly so the engineer doesn't
        mistake the V1b warning for a successful init.
        """
        if self.emulation:
            self.log.info("DUT_U300.cmd_initialize: emulation no-op")
            return
        raise NotImplementedError(
            "DUT_U300.cmd_initialize: the rfd_simulator register-map init "
            "path from the original UMT_DUTs/DUT_U300.py is not yet ported. "
            "Engineer must wire the real init flow (or set "
            "config.dut.emulation: true to bypass) before bench validation.")

    # rfTxStop
    def set_rfTxStop(self) -> None:
        """Configure TX Stop.

        V1f audit: on real hardware this raises ``NotImplementedError``
        rather than silently no-op'ing — the source-level body programs
        RFIC + RFFE stop registers, and silently skipping that leaves the
        DUT in an undefined state at the end of the test.
        """
        if self.emulation:
            self.log.info("DUT_U300.set_rfTxStop: emulation no-op")
            return
        raise NotImplementedError(
            "DUT_U300.set_rfTxStop: real-hardware Tx-stop register sequence "
            "not yet ported from UMT_DUTs/DUT_U300.py. Engineer must port "
            "before bench validation (or set config.dut.emulation: true).")

    # rfTxPower
    def set_rfTxPower(
        self,
        ul_powers_dBm: float = 24.00,
        backoffs_dB: float = 0.0,
        rb_centre_frequency_Hz: float = 15e3,
        pll_frequency_Hz: float = 2500000000,
        backoff_mode: str = "auto",
        antenna_config: str = "ANT0",
        scs_Hz: float = 15e3,
    ):
        """Set TX power for a specific carrier, and switch to the specified antenna(s).

        Args:
            ul_powers_dBm: Target power in dBm for the Tx at the antenna.
            backoffs_dB: Backoff used for MPR in dB.
            pll_frequency_Hz: TX frequency in Hz
            rb_centre_frequency_Hz: Absolute center frequency of the allocation in KHz.

        Returns:
            pwr: power at the antenna (dBm)
            rfic_lut_idx: no rfic_lut_idx returned -> value is -1
            pa_lut_idx: no pa_lut_idx returned -> value is -1
            dac_bo: DAC backoff in dBFS
        """
        if self.emulation:
            self.log.info(
                "DUT_U300.set_rfTxPower: emulation — returning canned tuple "
                "(target=%.2f dBm)", ul_powers_dBm
            )
            # Canned values: target met exactly, no LUT info, zero DAC backoff.
            return (ul_powers_dBm, -1, -1, 0.0)

        # V1f audit: previously this silently returned the same canned
        # tuple on bench, which would mask a missing port — the engineer
        # would see "tx_power=0.0 dBm exactly" in every result row and
        # assume the RFIC was working. Now it fails loudly.
        raise NotImplementedError(
            "DUT_U300.set_rfTxPower: real-hardware RFIC + RFFE power-set "
            "sequence not yet ported from UMT_DUTs/DUT_U300.py. The method "
            "returns a (pwr, rfic_lut_idx, pa_lut_idx, dac_bo) tuple — "
            "until the real implementation lands the only safe behavior "
            "is to fail. Set config.dut.emulation: true to use canned "
            f"values during framework debugging (target was {ul_powers_dBm} dBm).")

    def set_arb_power_dBFSrms(
        self,
        wfg: WFG = None,
        power_dBFSrms: float = -13.0,
        deembedding: float = 0.5,
        IpFS: float = 0.001,
        R: float = 650,
        i_offset_A: float = 0.0,
        q_offset_A: float = 0.0,
        iq_gain_imbalance_dB: float = 0,
        iq_phase_imbalance_deg: float = 0,
        scs_Hz: float = 15e3,
        rfbw_Hz: float = 10e6,
        ul_frequency_Hz: float = 2.5e9,
        band: str = "n1",
    ) -> None:
        """Adjusts WFG output power.

        Args:
            power_dBFSrms: requested power level as with reference to the peak power
            VppFS: peak voltage (Vp) for a full-scale signal on resistor of the RFHB buffer
            deembedding: scale from the connector to the voltage at the resistor Vres/Vcon
            R (float): resistor on the host board V/I
            filter: use "OFF" or "NORMal"
            iq_gain_imbalance_dB (float): IQ gain imbalance in dB
            iq_phase_imbalance_deg (float): IQ phase imbalance in deg
            i_offset_A (float): I offset in A
            q_offset_A (float): Q offset in A
            ul_frequency_Hz (float): RF frequency of the UL in Hz
            scs_Hz (float): sub-carrier spacing (SCS) in Hz
            band (string): band identifier (according to 3GPP; with 'n' for 5G and 'B' for LTE)
        """
        # Source body was 'pass' — already a no-op. Preserved here so the migrated
        # TX EVM test can call this method without raising NotImplementedError.
        if self.emulation:
            self.log.info("DUT_U300.set_arb_power_dBFSrms: emulation no-op")
            return
        self.log.warning("set_arb_power_dBFSrms: real-hardware path not ported in V1b")

    #
    # set_arb_signal_bb("5G", "QPSK", 10e6, -13)
    # set_arb_signal_bb("CW", "1MHz", power_dBFSrms=-3)
    # set_arb_signal_bb("Two-tone", "1MHz_1.1MHz", power_dBFSrms=-3)
    #
    def set_arb_signal_bb(
        self,
        wfg: WFG = None,
        signal_type: str = "5G",
        signal_option: str = "QPSK",
        signal_frequency_Hz: float = 1e6,
        bw_Hz: float = 10e6,
        power_dBFSrms: float = -13.0,
        deembedding: float = 0.5,
        IpFS: float = 0.001,
        R: float = 650,
        filter: str = "OFF",
        iq_gain_imbalance_dB: float = 0,
        iq_phase_imbalance_deg: float = 0,
        i_offset_A: float = 0.0,
        q_offset_A: float = 0.0,
        ul_frequency_Hz: float = 2.5e9,
        scs_Hz: float = 30e3,
        band: str = "n1",
    ) -> None:
        """Sets WFG-driven baseband signal.

        Args:
            power_dBFSrms (float): requested power level as with reference to the peak power
            VppFS (float): peak voltage (Vp) for a full-scale signal on resistor of the RFHB buffer
            deembedding (float): scale from the connector to the voltage at the resistor Vres/Vcon
            R (float): resistor on the host board V/I
            filter: use "OFF" or "NORMal"
            iq_gain_imbalance_dB (float): IQ gain imbalance in dB
            iq_phase_imblalance_deg (float): IQ phase imbalance in deg
            i_offset_A (float): I offset in A
            q_offset_A (float): Q offset in A
            ul_frequency_Hz (float): RF frequency of the UL in Hz
            scs_Hz (float): sub-carrier spacing (SCS) in Hz
            band (string): band identifier (according to 3GPP; with 'n' for 5G and 'B' for LTE)

        Returns:
            None
        """
        # Source body was 'pass' — already a no-op. Preserved here so the migrated
        # TX EVM test can call this method without raising NotImplementedError.
        if self.emulation:
            self.log.info("DUT_U300.set_arb_signal_bb: emulation no-op")
            return
        self.log.warning("set_arb_signal_bb: real-hardware path not ported in V1b")

    def get_BandNumber(self, band: str = "n41"):
        """Convert band code (as per 3GPP) to a band-number.

        Args:
            band (str): band-code as per 3GPP (e.g., n41, B7, n28A, ..), default is n41

        Returns:
            band_number as integer
        """
        try:
            band_num = int(band.lstrip("n"))
            return band_num
        except ValueError:
            if band == "n28A" or band == "B28A":
                return 281
            if band == "n28B" or band == "B28B":
                return 282
            return None

    def dBm2dBV(self, x, Z0=50):
        """Convert a dBm value for the Rx into dBV considering Z0.

        Args:
            x (float): power level in dBm for a complex signal in dBm
            Z0 (float): Impedance Z0 in (ohms)

        Returns:
            y (float): power level in dBV
        """
        return float(x + 10 * np.log10(Z0) - 10 * np.log10(1000) + 10 * np.log10(2))

    def dBV2dBm(self, x, Z0=50):
        """Convert a dBV value for the Rx into dBm considering Z0.

        Args:
            x (float): power level in dBm for a complex signal in dBm
            Z0 (float): Impedance Z0 in (ohms)

        Returns:
            y (float): power level in dBV
        """
        return float(x - 10 * np.log10(Z0) + 10 * np.log10(1000) - 10 * np.log10(2))
