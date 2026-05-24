"""CMW100AMixin -- analyzer-side measurement methods for the R&S CMW100.

Ported from UMT_Instruments/CMW100A.py minus the OpenTAP scaffolding. Only the
methods used by the U300B0 TX EVM Power Sweep demo (setup_NrTx, meas_NrTxAll,
meas_NrTxEVM, meas_NrTxPower) are ported in V1a; other measurements port on
demand as more tests migrate.
"""
from __future__ import annotations

import logging
import math

from RsCmwGprfGen import *
from RsCmwGprfMeas import *
from RsCmwLteMeas import *
from RsCmwLteSig import *
from RsCmwNrFr1Meas import *

# The base package is distributed on PyPI as `rscmw-base` and imports as
# `rscmw_base` (lowercase + underscore), not `RsCmwBase`. The legacy source
# used `from RsCmwBase import *`; we tolerate either form so the module loads
# in environments where only one of the two packaging schemes is installed.
try:
    from RsCmwBase import *  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover -- exercised on V1b hardware only
    try:
        from rscmw_base import RsCmwBase  # type: ignore[import-not-found]
    except ImportError:
        RsCmwBase = None  # type: ignore[assignment]

import re
import time

import numpy as np
import RsCmwNrFr1Meas.enums as NrFr1Meas_enums
import RsCmwNrFr1Meas.repcap as NrFr1Meas_repcap


class CMW100AMixin:

    GprfMeas = None
    Base = None
    LteMeas = None
    Nrfr1Meas = None
    VisaAddress = None
    is_emulation = False
    # in_synchronization_mode is set by the CMW100 façade (mirrors the OpenTAP
    # default "Enhanced"). Declared here so static type-checkers see it.
    in_synchronization_mode: str = "Enhanced"
    # Per-antenna RF connector indices used when `in_ul_config` resolves to
    # ANT0 / ANT1 (e.g. "ANT0", "TX0_ANT0"). Defaults are R11 / R12 — matches
    # the U300B0 EVT bench layout. Engineers can override on the instance
    # before calling setup_NrTx if the DUT routes antennas elsewhere.
    in_rf_connector_ant0: int = 1
    in_rf_connector_ant1: int = 2

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.freq_start = 0
        self.freq_stop = 0
        self.err_list = None
        self.delay_pre_measurement = 3
        self.delay_pre_fetch = 0.2

    def Open(self, VisaAddress):

        if self.is_emulation:
            return

        self.VisaAddress = VisaAddress
        if self.VisaAddress!=None:
            self.GprfMeas = RsCmwGprfMeas(self.VisaAddress)
            self.Base = RsCmwBase(self.VisaAddress)
            self.LteMeas = RsCmwLteMeas(self.VisaAddress)
            self.Nrfr1Meas = RsCmwNrFr1Meas(self.VisaAddress)
        else:
            pass
            #self.log.warning("VisaAddress is not defined")

    def Close(self):

        if self.is_emulation:
            return

        if self.GprfMeas is not None:
            self.GprfMeas.close()
        if self.Base is not None:
            self.Base.close()
        if self.LteMeas is not None:
            self.LteMeas.close()
        if self.Nrfr1Meas is not None:
            self.Nrfr1Meas.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_rf_connector(self, in_ul_config, in_rf_connector):
        """Pick the RF input connector index based on the UL antenna config.

        The original OpenTAP code only recognized exact ``"ANT0"`` / ``"ANT1"``
        strings, which crashed with ``UnboundLocalError`` on any other value
        (including the ``"TX0_ANT0"`` / ``"TX0_ANT1"`` forms the U300B0 EVT
        configs actually use — discovered on bench SZLABPC-WIN04 in
        v1.0.0-rc8 bring-up). v1.0.0-rc9 generalizes the match:

        - ``None``                  → ``in_rf_connector`` (caller's explicit pick)
        - any string ending in ``"ANT0"`` → ``self.in_rf_connector_ant0``
        - any string ending in ``"ANT1"`` → ``self.in_rf_connector_ant1``
        - anything else             → ``in_rf_connector`` + warning log

        The "ends with" match handles ``ANT0`` / ``TX0_ANT0`` / ``TX1_ANT0``
        uniformly: in every bench layout we've seen, the antenna index
        determines which physical R1x port to use, not the TX-path prefix.
        """
        if isinstance(in_ul_config, str):
            if in_ul_config.endswith("ANT0"):
                return self.in_rf_connector_ant0
            if in_ul_config.endswith("ANT1"):
                return self.in_rf_connector_ant1
            self.log.warning(
                "setup_NrTx: in_ul_config=%r not recognized; "
                "falling back to in_rf_connector=%s",
                in_ul_config, in_rf_connector)
        return in_rf_connector

    def setup_NrTx(self, in_band='n41', in_freq_pll_Hz=2.5E9, in_rfbw_Hz=5E6,
                    in_rb_centre_freq_Hz=15000, in_tx_power_dBm=5,
                    in_tx_power_backoff_dB = 0, in_modulation="16QAM",
                    in_ul_config = None, in_rf_connector = 1, in_scs_Hz=30e3,
                    in_synchronization_mode = None):

        #in_band='n41', in_freq_pll_Hz=2.5E9, in_rfbw_Hz=5E6, in_rb_centre_freq_Hz=0, in_tx_power_dBm=-25
        # nothing to do for emulation
        if self.is_emulation:
            return


        rf_con = self._resolve_rf_connector(in_ul_config, in_rf_connector)

        fdd = [1,2,3,4,5,7,8,12,13,14,18,20,24,25,26,28,30,31,65,66,70,71,72,74,85,91,92,93,94,100,105,106,109]
        tdd = [34,38,39,40,41,48,50,51,53,54,77,78,79,90,96,101,102,104]

        x = re.sub(r'[a-zA-Z_]','', in_band)
        band_number = int(x)

        #================Check Band is FDD or TDD + Convert Bw to MHz Only======================#
        bw_MHz  = float(in_rfbw_Hz)/1e6
        scs_KHz = float(in_scs_Hz)/1e3
        # *****************************************************************************
        # Set duplex mode FDD.
        # *****************************************************************************
        if band_number in fdd:
            self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_dmode(NrFr1Meas_enums.DuplexModeB.FDD)
        if band_number in tdd:
            self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_dmode(NrFr1Meas_enums.DuplexModeB.TDD)
        # *****************************************************************************
        # Define the RF input path.
        # *****************************************************************************
        if rf_con==1:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R11)
        elif rf_con==2:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R12)
        elif rf_con==3:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R13)
        elif rf_con==4:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R14)
        elif rf_con==5:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R15)
        elif rf_con==6:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R16)
        elif rf_con==7:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R17)
        elif rf_con==8:
            self.Nrfr1Meas.route.nrSubMeas.rfSettings.set_connector(NrFr1Meas_enums.RxConnector.R18)
        else:
            return None
        # *****************************************************************************
        # Configure RF and analyzer settings:
        # External attenuation 0 dB, peak power -5 dBm, 2 dB user margin
        #*****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.rfSettings.set_eattenuation(0)
        self.Nrfr1Meas.configure.nrSubMeas.rfSettings.set_envelope_power(in_tx_power_dBm+20.0)
        self.Nrfr1Meas.configure.nrSubMeas.rfSettings.set_umargin(0)
        # *****************************************************************************
        # Setting PhaseNR_UL Compensation OFF by default
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.pcomp.set(NrFr1Meas_enums.PhaseComp.OFF,user_def_freq = in_freq_pll_Hz)
        # *****************************************************************************
        # Set NS01 as standard test case
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_ns_value(NrFr1Meas_enums.NetworkSigVal.NS01)

        # *****************************************************************************
        # Enable carrier aggregation with one carriers.
        # Use CC1 for synchronization and single-carrier measurements.
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.set_ncarrier(1)
        self.Nrfr1Meas.configure.nrSubMeas.listPy.segment.caggregation.mcarrier.set(NrFr1Meas_enums.CarrierComponent.CC1, NrFr1Meas_repcap.SEGMent.Default)
        # *****************************************************************************
        # Define the band
        # *****************************************************************************
        def format_band(band_number):
            band_str = str(band_number)
            return f'OB{band_str}'
        band_cmw = format_band(band_number)
        band_param = getattr(NrFr1Meas_enums.Band, band_cmw)

        self.Nrfr1Meas.configure.nrSubMeas.set_band(band_param)
        # *****************************************************************************
        # Define the channel bandwidths
        # *****************************************************************************
        def format_bandwidth(bw_MHz):
            # Convert the input to a string
            bw_str = str(int(bw_MHz))
            # Determine the length of the input and format accordingly
            if len(bw_str) == 1:
                return f'B00{bw_str}'
            elif len(bw_str) == 2:
                return f'B0{bw_str}'
            elif len(bw_str) == 3:
                return f'B{bw_str}'
            else:
                raise ValueError("Input should be a 1, 2, or 3 digit number")
        bw_cmw = format_bandwidth(bw_MHz)
        bandwidth_param = getattr(NrFr1Meas_enums.ChannelBwidth, bw_cmw)

        self.Nrfr1Meas.configure.nrSubMeas.cc.cbandwidth.set(bandwidth_param, NrFr1Meas_repcap.CarrierComponent.Default)
        # *****************************************************************************
        # Configure the frequencies:
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.cc.frequency.set(in_freq_pll_Hz)
        # *****************************************************************************
        #Set Physical Cell ID and DMRS Type A Position
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.cc.plcId.set(1)
        self.Nrfr1Meas.configure.nrSubMeas.cc.taPosition.set(2)
        # *****************************************************************************
        #Set Sub Carrier Spacing and Offset to carrier
        # *****************************************************************************
        def format_scs(scs_KHz):
            scs_str = str(int(scs_KHz))
            return f'S{scs_str}K'
        scs_cmw = format_scs(scs_KHz)
        scs_param = getattr(NrFr1Meas_enums.SubCarrSpacing, scs_cmw)
        self.Nrfr1Meas.configure.nrSubMeas.ccall.txBwidth.set_sc_spacing(scs_param)
        self.Nrfr1Meas.configure.nrSubMeas.cc.txBwidth.offset.set(0)
        # *****************************************************************************
        # Specify bandwidth part settings for CC1.
        # *****************************************************************************
        def get_bandwidth_part_max_rbs(bw_MHz, scs_KHz):
            if int(scs_KHz) == 15:
                bw_to_rbs = {
                    5: 25,
                    10: 52,
                    15: 79,
                    20: 106,
                    25: 133,
                    30: 160,
                    35: 188,
                    40: 216,
                    45: 242,
                    50: 270
                }
            elif int(scs_KHz) == 30:
                bw_to_rbs = {
                    5: 11,
                    10: 24,
                    15: 38,
                    20: 51,
                    25: 65,
                    30: 78,
                    35: 92,
                    40: 106,
                    45: 119,
                    50: 133,
                    60: 162,
                    70: 189,
                    80: 217,
                    90: 245,
                    100: 273
                }
            else:
                return None

            return bw_to_rbs.get(bw_MHz, None)
        self.Nrfr1Meas.configure.nrSubMeas.cc.bwPart.set(NrFr1Meas_enums.BandwidthPart.BWP0,
            scs_param, NrFr1Meas_enums.CyclicPrefix.NORMal,
            number_rb = get_bandwidth_part_max_rbs( bw_MHz, scs_KHz), start_rb = 0)
        if in_modulation=="QPSK":
            add_position = 1
        elif in_modulation=="16QAM":
            add_position = 1
        elif in_modulation=="64QAM":
            add_position = 0
        elif in_modulation=="256QAM":
            add_position = 0
        else:
            raise ValueError("Modulation shall be QPSK, 16QAM, 64QAM, or 256QAM")
        self.Nrfr1Meas.configure.nrSubMeas.cc.bwPart.pusch.dmta.set(NrFr1Meas_enums.BandwidthPart.BWP0,
                config_type = 1, add_position = add_position, max_length = 1)
        self.Nrfr1Meas.configure.nrSubMeas.cc.bwPart.pusch.dmtb.set(NrFr1Meas_enums.BandwidthPart.BWP0,
                config_type = 1, add_position = add_position, max_length = 1)
        self.Nrfr1Meas.configure.nrSubMeas.cc.bwPart.pusch.dftPrecoding.set(NrFr1Meas_enums.BandwidthPart.BWP0,
                dft_precoding = False)
        # *****************************************************************************
        # Specify PUSCH allocation for CC1.
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.cc.nallocations.set(1)
        structure =  self.Nrfr1Meas.configure.nrSubMeas.cc.allocation.pusch.PuschStruct()
        structure.Mapping_Type =  NrFr1Meas_enums.MappingType.A
        structure.No_Symbols = 14
        structure.Start_Symbol = 0
        structure.Auto = False
        structure.No_Rbs = get_bandwidth_part_max_rbs( bw_MHz, scs_KHz)/2-2
        structure.Start_Rb = 0
        if in_modulation=="QPSK":
            structure.Mod_Scheme = NrFr1Meas_enums.ModulationScheme.QPSK
        elif in_modulation=="16QAM":
            structure.Mod_Scheme = NrFr1Meas_enums.ModulationScheme.Q16
        elif in_modulation=="64QAM":
            structure.Mod_Scheme = NrFr1Meas_enums.ModulationScheme.Q64
        elif in_modulation=="256QAM":
            structure.Mod_Scheme = NrFr1Meas_enums.ModulationScheme.Q256
        else:
            raise ValueError("Modulation shall be QPSK, 16QAM, 64QAM, or 256QAM")
        self.Nrfr1Meas.configure.nrSubMeas.cc.allocation.pusch.set(structure)
        self.Nrfr1Meas.configure.nrSubMeas.cc.allocation.pusch.additional.set(dmrs_length = 1, antenna_port =0 )
        self.Nrfr1Meas.configure.nrSubMeas.cc.allocation.pusch.sgeneration.set(initialization = NrFr1Meas_enums.Generator.PHY, dmrs_id = 0, nscid = 0)
        # *****************************************************************************
        # Set Measurement to be continuous
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_repetition(repetition = enums.Repeat.CONTinuous)
        # *****************************************************************************
        # Define measurement timeout, stop condition, error handling, RB filter.
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_timeout(timeout = 10)
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_scondition(NrFr1Meas_enums.StopCondition.NONE)
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_mo_exception(meas_on_exception = False)
        #self.Nrfr1Meas.configure.nrSubMeas.multiEval.set_nvfilter(nrb_view_filter = 0)
        # *****************************************************************************
        # Define the scope of the measurement:
        # Capture all 10 subframes of radio frames. Measure all slots of the subframes.
        # *****************************************************************************
        #self.Nrfr1Meas.configure.nrSubMeas.multiEval.msubFrames.set(sub_frame_offset = 0, sub_frame_count = 10, meas_subframe = 1)
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.mslot.set(NrFr1Meas_enums.MeasureSlot.ALL, meas_slot_no = 0)

        # *****************************************************************************
        # Specify modulation measurement settings:
        # Disable tracking, define TX DC location offset,
        # measurement over 20 statistics cycles, EVM window length for BW 40 MHz.
        # *****************************************************************************
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.modulation.tracking.set_level(level = False)
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.modulation.tracking.set_phase(phase = False)
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.modulation.tracking.set_timing(timing = False)
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.modulation.set_tdl_offset(offset = 0)
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.scount.set_modulation(statistic_count = 10)

        # *****************************************************************************
        # Set trigger source, timeout, trigger level, slope, delay,
        # minimum trigger gap, synchronization mode and frame synchronization.
        # *****************************************************************************

        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_source(source = 'Free Run (Fast Sync)')
        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_timeout(trigger_timeout = 1)
        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_threshold(trig_threshold = -20)
        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_slope(slope = NrFr1Meas_enums.SignalSlope.REDGe)
        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_delay(delay = 0)
        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_mgap(min_trig_gap = 0)

        if in_synchronization_mode is None:
            if self.in_synchronization_mode=="Enhanced":
                smode = NrFr1Meas_enums.SyncMode.ENHanced
            elif self.in_synchronization_mode=="Normal":
                smode = NrFr1Meas_enums.SyncMode.NORMal
            elif self.in_synchronization_mode=="Enhanced Single Slot":
                smode = NrFr1Meas_enums.SyncMode.ESSLot
            elif in_synchronization_mode=="Normal Single Slot": # Normal Single Slot
                smode = NrFr1Meas_enums.SyncMode.NSSLot
            else:
                smode = NrFr1Meas_enums.SyncMode.NORMal
        elif in_synchronization_mode=="Enhanced":
            smode = NrFr1Meas_enums.SyncMode.ENHanced
        elif in_synchronization_mode=="Normal":
            smode = NrFr1Meas_enums.SyncMode.NORMal
        elif in_synchronization_mode=="Enhanced Single Slot":
            smode = NrFr1Meas_enums.SyncMode.ESSLot
        elif in_synchronization_mode=="Normal Single Slot": # Normal Single Slot
            smode = NrFr1Meas_enums.SyncMode.NSSLot
        else:
            smode = NrFr1Meas_enums.SyncMode.NORMal

        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_smode(sync_mode = smode)
        self.Nrfr1Meas.trigger.nrSubMeas.multiEval.set_fsync(frame_sync=True)
        #time.sleep(0.1)

        structure =  self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.AllStruct()
        structure.Evm = False
        structure.Magnitude_Error = False
        structure.Phase_Error = False
        structure.Inband_Emissions = False
        structure.Evm_Versus_C = False
        structure.Iq = False
        structure.Equ_Spec_Flatness = False
        structure.Tx_Measurement = False
        structure.Spec_Em_Mask = False
        structure.Aclr = False
        structure.Power_Monitor = False
        structure.Power_Dynamics = False
        structure.Tx_Power = True
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.set_all(value = structure)

        # Expected power adjustment
        self.Nrfr1Meas.nrSubMeas.multiEval.initiate()
        tx_power = self.Nrfr1Meas.nrSubMeas.multiEval.txPower.current.fetch()
        Error = tx_power.Reliability
        Exp_Power = self.Nrfr1Meas.configure.nrSubMeas.rfSettings.get_envelope_power()

        max_iterations = 10
        iteration = 0

        # Overdriven
        if Error == 3:
            while Error == 3 and Exp_Power <= 40 and iteration < max_iterations:
                Exp_Power += 10
                #self.log.warning(f"[Overdriven] Iteration {iteration}: Increasing Exp_Power to {Exp_Power}")
                self.Nrfr1Meas.configure.nrSubMeas.rfSettings.set_envelope_power(Exp_Power)
                time.sleep(self.delay_pre_measurement)
                self.Nrfr1Meas.nrSubMeas.multiEval.initiate()
                time.sleep(self.delay_pre_fetch)
                tx_power = self.Nrfr1Meas.nrSubMeas.multiEval.txPower.current.fetch()
                Error = tx_power.Reliability
                iteration += 1

        # Underdriven
        elif Error == 4:
            while Error == 4 and Exp_Power >= -45 and iteration < max_iterations:
                Exp_Power -= 10
                #self.log.warning(f"[Underdriven] Iteration {iteration}: Decreasing Exp_Power to {Exp_Power}")
                self.Nrfr1Meas.configure.nrSubMeas.rfSettings.set_envelope_power(Exp_Power)
                time.sleep(self.delay_pre_measurement)
                self.Nrfr1Meas.nrSubMeas.multiEval.initiate()
                time.sleep(self.delay_pre_fetch)
                tx_power = self.Nrfr1Meas.nrSubMeas.multiEval.txPower.current.fetch()
                Error = tx_power.Reliability
                iteration += 1
        self.Nrfr1Meas.nrSubMeas.multiEval.initiate()

    # *****************************************************************************
    # Enable all measurements.
    # *****************************************************************************
    def meas_NrTxAll(self):

        # nothing to do for emulation
        if self.is_emulation:
            return

        structure =  self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.AllStruct()
        structure.Evm = True
        structure.Magnitude_Error = True
        structure.Phase_Error = True
        structure.Inband_Emissions = True
        structure.Evm_Versus_C = True
        structure.Iq = True
        structure.Equ_Spec_Flatness = True
        structure.Tx_Measurement = True
        structure.Spec_Em_Mask = True
        structure.Aclr = True
        structure.Power_Monitor = True
        structure.Power_Dynamics = True
        structure.Tx_Power = True
        self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.set_all(value = structure)

        # *****************************************************************************
        # Initiate all measurements.
        # *****************************************************************************
        time.sleep(self.delay_pre_measurement)
        self.Nrfr1Meas.nrSubMeas.multiEval.initiate()

    # *****************************************************************************
    # EVM measurements.
    # *****************************************************************************
    def meas_NrTxEVM(self, use_cached=False):

        # return a dummy value
        if self.is_emulation:
            return 2.0 + np.random.rand()

        if not use_cached:
            # *****************************************************************************
            # Enable measurements.
            # *****************************************************************************
            structure =  self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.AllStruct()
            structure.Evm = True
            structure.Magnitude_Error = False
            structure.Phase_Error = False
            structure.Inband_Emissions = False
            structure.Evm_Versus_C = False
            structure.Iq = False
            structure.Equ_Spec_Flatness = False
            structure.Tx_Measurement = False
            structure.Spec_Em_Mask = False
            structure.Aclr = False
            structure.Power_Monitor = False
            structure.Power_Dynamics = False
            structure.Tx_Power = False
            self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.set_all(value = structure)

            # *****************************************************************************
            # Initiate all measurements.
            # *****************************************************************************
            time.sleep(self.delay_pre_measurement)
            self.Nrfr1Meas.nrSubMeas.multiEval.initiate()

        #Evm_each_slot = self.Nrfr1Meas.nrSubMeas.multiEval.cc.evMagnitude.maximum.fetch(carrierComponent = repcap.CarrierComponent.Default)
        Evm_each_slot = self.Nrfr1Meas.nrSubMeas.multiEval.cc.evMagnitude.average.fetch(carrierComponent = repcap.CarrierComponent.Default)
        self.get_NrErrors()

        def calculate_average(numbers):
            if not numbers:
                return 0
            return sum(numbers) / len(numbers)
        out_evm_pct = calculate_average(Evm_each_slot.Low+Evm_each_slot.High)

        return out_evm_pct

    #******************************************************************************
    # Tx power measurements.
    # *****************************************************************************
    def meas_NrTxPower(self, use_cached = False, n_retry=5):

        # return a dummy value
        if self.is_emulation:
            return 23 + np.random.rand()


        if not use_cached:
            # *****************************************************************************
            # Enable measurements.
            # *****************************************************************************
            structure =  self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.AllStruct()
            structure.Evm = False
            structure.Magnitude_Error = False
            structure.Phase_Error = False
            structure.Inband_Emissions = False
            structure.Evm_Versus_C = False
            structure.Iq = False
            structure.Equ_Spec_Flatness = False
            structure.Tx_Measurement = False
            structure.Spec_Em_Mask = False
            structure.Aclr = False
            structure.Power_Monitor = False
            structure.Power_Dynamics = False
            structure.Tx_Power = True
            self.Nrfr1Meas.configure.nrSubMeas.multiEval.result.set_all(value = structure)

            # *****************************************************************************
            # Initiate all measurements.
            # *****************************************************************************
            #self.Nrfr1Meas.nrSubMeas.multiEval.initiate()

        for i in range(0, n_retry):

            if not use_cached:
                time.sleep(self.delay_pre_measurement)
                self.Nrfr1Meas.nrSubMeas.multiEval.initiate()
            time.sleep(self.delay_pre_fetch)
            #tx_power = self.Nrfr1Meas.nrSubMeas.multiEval.txPower.average.fetch()
            tx_power = self.Nrfr1Meas.nrSubMeas.multiEval.txPower.average.fetch()
            self.get_NrErrors()
            if not math.isnan(tx_power.Tx_Power):
                return tx_power.Tx_Power

        return tx_power.Tx_Power
