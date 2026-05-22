"""

U300B0_RFEB_EVT_TX_EVM_Power_Sweep -- Testcase to run a TX EVM measurement sweeping over power

Attributes:
    Title:   U300B0_RFEB_EVT_TX_EVM_Power_Sweep.py
    Authors: Amaury Deplanque, Sina Mahani, Gernot Hueber
    Copyright: Copyright 2026, Amaury Deplanque, Sina Mahani, Gernot Hueber
    License: GPL
    Version: 1.0.0
    Email: gernot.hueber@bc-s.com
"""

__author__ = "Gernot Hueber"
__copyright__ = "Copyright 2024, Gernot Hueber"
__credits__ = ["Gernot Hueber"]
__license__ = "GPL"
__version__ = "0.0.1"
__maintainer__ = "Gernot Hueber"
__email__ = "gernot.hueber@umsemi.com"
__status__ = "Production"


import clr
import OpenTap
from opentap import *
from System import String

clr.AddReference("System.Collections")
clr.AddReference("OpenTap.Plugins.BasicSteps")
import math
import time

import numpy as np
from opentap import *
from U300_RFEngine.Calibration_File import Calibration_File
from U300_RFEngine.Deembedding import Deembedding
from U300_RFEngine.Testconditions_Limits import Testconditions_Limits
from UMT_DUTs.UMT_DUT import UMT_DUT  # DUT for SPI Write
from UMT_Instruments.CMW100 import CMW100
from UMT_Instruments.DMM import DMM
from UMT_Instruments.WFG import WFG

from .U300_RFEngine_EVT_Base import U300_RFEngine_EVT_Base

# Here is how a test step plugin is defined:

#Use the Display attribute to define how the test step should be presented to the user.
#@attribute(OpenTap.Display(Name="U300 RFEngine 5G NR Tx EVM", Description="Tx EVM (U300-RFE-DVT-000-07)", group=["U300 RFEngine", "DVT"]))
@attribute(OpenTap.Display("U300B0_RFEB_EVT_TX_EVM_Power_Sweep", "Tx EVM Sweep (U300B0-RFE-EVT-005)", "U300B0 RFEngine EVT"))
#AllowAnyChildAttribute is attribute that allows any child step to attached to this step
@attribute(OpenTap.AllowAnyChild())
class U300B0_RFEB_EVT_TX_EVM_Power_Sweep(U300_RFEngine_EVT_Base): # Inheriting from opentap.TestStep causes it to be a test step plugin.
    # Add properties (name, value, C# type
    # Metadata information to store
    Testcase_ID = property(String, "U300B0-RFE-EVT-005") \
        .add_attribute(OpenTap.Display("Testcase_ID", "Testcase Identifier")) \
        .add_attribute(OpenTap.MetaData(True))

    #
    cmw100 = property(CMW100, None)\
        .add_attribute(OpenTap.Display("CMW100", "CMW100 for Tx Measurements", "Instruments"))
    wfg = property(WFG, None)\
        .add_attribute(OpenTap.Display("WFG", "WFG for Tx Measurements", "Instruments"))
    dut = property(UMT_DUT, None)\
        .add_attribute(OpenTap.Display("DUT", "Any UMT_DUT", "DUT"))
    dmm_c = property(DMM, None)\
        .add_attribute(OpenTap.Display("DMM_C", "DMM for current measurements", "Instruments"))
    dmm_v = property(DMM, None)\
        .add_attribute(OpenTap.Display("DMM_V", "DMM for voltage measurements", "Instruments"))

    # output parameters
    out_modulation = None
    out_EVM_pct = None
    out_tx_power_dBm = None
    out_target_tx_power_dBm = None
    out_modulation = None
    out_tx_power_lut_idx = None
    out_tx_rfic_lut_idx = None
    out_tx_pa_lut_idx = None
    out_backoff_dB = None
    out_tx_power_rfd_dBm = None
    out_tx_backoff_dB = None

    #
    # INSTRUMENTS
    # {'cmw': '0 (1)', 'spectrum_analyzer': '1 (0)', 'vector_signal_generator': '1 (0)', 'oscilloscope': 1, 'baseband_signal_generator': 1, 'vsa': 1, 'psu': 1, 'vna': 1, 'dmm': 0}
    # - cmw: 0 (1)
    # - spectrum_analyzer: 1 (0)
    # - vector_signal_generator: 1 (0)
    # - oscilloscope: 1
    # - baseband_signal_generator: 1
    # - vsa: 1
    # - psu: 1
    # - vna: 1
    # - dmm: 0
    #

    def __init__(self):
        super().__init__() # The base class initializer must be invoked.


    def PreRun():
        super().PreRun()

    def PostRun():
        super().PostRun()

    def Run(self):
        super().Run() ## 3.0: Required for debugging to work.

        self.Setup_DMM()

        # get testcase conditions and limits
        tc_cond_limits = Testconditions_Limits(self.in_conditions_limits_config)
        target_tx_power = self.in_tx_power_dBm

        # read deembedding (loss) data
        deembedding = Deembedding(self.in_deembedding_config)
        deemb_rfeb, deemb_ant, deemb_bb, deemb_coupler = deembedding.get(top='TX', uldl_config=self.in_ul_config,
                                                        band=self.in_band, frequency=self.in_ul_freq_pll_Hz)
        if deemb_rfeb is None or \
            deemb_ant is None or \
            deemb_bb is None:
            self.log.Error("Deembedding data cannot be read")
            return

        # get calibration file data
        cal_file = Calibration_File(self.in_calibration_file_config, self.RFEB_SN, self.RFHB_SN)
        i_offset_A, q_offset_A = cal_file.get_iq_dc_offset(in_band_num=self.dut.get_BandNumber(self.in_band), in_rfbw_Hz=self.in_rfbw_Hz)
        iq_gain_imbalance_dB, iq_phase_imbalance_deg = cal_file.get_iq_gain_phase_imbalance(self.dut.get_BandNumber(self.in_band), self.in_rfbw_Hz)

        # setup RFIC+RFFE
        pwr, backoff = self.initialize_tx(target_tx_power=target_tx_power)

        #
        # TESTCASE DESCRIPTION
        #
        # - Supply RFIC (1.4V, 1.8V, 2.5V, CIFPMUEN=high, nRST=low); |br| write/read full register map, then put RFIC into reset & CIFPMUEN=off continuously for 24hrs; |br| capture number of data errors

        #for modulation in ["QPSK", "16QAM", "64QAM", "256QAM"]:
        for modulation in ["16QAM"]:

            target_evm_max = tc_cond_limits.get_band_modulation(self.__class__.__name__, band=self.in_band,
                                            modulation=modulation, param = 'EVM_MAX')
            target_evm_margin = tc_cond_limits.get_band_modulation(self.__class__.__name__, band=self.in_band,
                                            modulation=modulation, param='EVM_MAX_margin')
            # configure and enable waveform generator
            try:
                self.dut.set_arb_signal_bb(wfg=self.wfg, signal_type="5G", signal_option=self.in_modulation, bw_Hz=self.in_rfbw_Hz,
                        power_dBFSrms=-backoff, deembedding=deemb_bb,
                        i_offset_A=i_offset_A, q_offset_A=q_offset_A,
                        iq_gain_imbalance_dB=iq_gain_imbalance_dB, iq_phase_imbalance_deg=iq_phase_imbalance_deg,
                        ul_frequency_Hz=self.in_ul_freq_pll_Hz, scs_Hz=self.in_scs_Hz,
                        band=self.in_band)
            except:
                    self.log.Warning("Unable to set BB signal, restart BB/RFIC")
                    pwr, backoff = self.initialize_tx(target_tx_power=target_tx_power, force_reboot=True)

            self.Print_Summary(modulation=modulation)

            for target_tx_power in np.arange(-45, 28+1, 1.0):

                try:
                    # first reduce the power from the WFG to a low value
                    self.dut.set_arb_power_dBFSrms(wfg=self.wfg, power_dBFSrms=-30, deembedding=deemb_bb,
                                i_offset_A=i_offset_A, q_offset_A=q_offset_A,
                                iq_gain_imbalance_dB=iq_gain_imbalance_dB, iq_phase_imbalance_deg=iq_phase_imbalance_deg,
                                scs_Hz=self.in_scs_Hz, rfbw_Hz=self.in_rfbw_Hz, ul_frequency_Hz=self.in_ul_freq_pll_Hz,
                                band=self.in_band)

                    pwr, self.out_tx_rfic_lut_idx, self.out_tx_pa_lut_idx, dac_bo = self.dut.set_rfTxPower(target_tx_power, self.in_tx_power_backoff_dB, self.in_rb_centre_freq_Hz,
                                                                        self.in_ul_freq_pll_Hz, backoff_mode="auto",
                                                                            antenna_config=self.in_ul_config, scs_Hz=self.in_scs_Hz)
                    backoff = (pwr-target_tx_power+self.in_tx_dac_backoff_dBFS)  # backoff: target versus what the RFIC+RFFE can achieve
                    self.dut.set_arb_power_dBFSrms(wfg=self.wfg, power_dBFSrms=-backoff, deembedding=deemb_bb,
                                i_offset_A=i_offset_A, q_offset_A=q_offset_A,
                                iq_gain_imbalance_dB=iq_gain_imbalance_dB, iq_phase_imbalance_deg=iq_phase_imbalance_deg,
                                scs_Hz=self.in_scs_Hz, rfbw_Hz=self.in_rfbw_Hz, ul_frequency_Hz=self.in_ul_freq_pll_Hz,
                                band=self.in_band)
                except:
                    self.log.Warning("Unable to set BB signal, restart BB/RFIC")
                    pwr, backoff = self.initialize_tx(target_tx_power=target_tx_power, force_reboot=True)
                    if pwr < -100:
                        return
                    continue

                # read measurement from CMW100
                if self.in_board_config=="RFEB1":
                    fe_gain_offset_dB = 0
                elif (self.in_board_config=="RFPB") & (target_tx_power<-4):
                    fe_gain_offset_dB = -12
                elif (self.in_board_config=="RFPB") & (target_tx_power>=-4):
                    fe_gain_offset_dB = -24
                else:
                    fe_gain_offset_dB = 0
                self.cmw100.setup_NrTx(in_band=self.in_band, in_freq_pll_Hz=self.in_ul_freq_pll_Hz,
                                    in_rfbw_Hz=self.in_rfbw_Hz, in_tx_power_dBm=target_tx_power+fe_gain_offset_dB,
                                    in_modulation=modulation, in_ul_config=self.in_ul_config, in_scs_Hz=self.in_scs_Hz)

                self.cmw100.meas_NrTxAll()
                tx_power = self.cmw100.meas_NrTxPower(use_cached=True)

                if math.isnan(tx_power):
                    self.log.Warning("CMW unable to report Tx Power level")
                    time.sleep(1)
                    continue

                self.out_EVM_pct = self.cmw100.meas_NrTxEVM(use_cached=True)
                if math.isnan(self.out_EVM_pct):
                    self.log.Warning("CMW unable to report Tx EVM")
                    time.sleep(1)
                    continue

                # compensate the measured power with the deembedding (losses)
                # and calculate the accurate (deviation from target)
                self.out_tx_power_dBm = tx_power - deemb_rfeb - deemb_ant
                self.out_target_tx_power_dBm = target_tx_power
                self.out_modulation = modulation
                self.out_tx_power_rfd_dBm = pwr
                self.out_tx_backoff_dB = backoff
                self.Get_Aux()
                self.Get_DMM()

                # Set verdict
                txmpr = self.dut.get_rfTxMPR(band=self.in_band, ofdm_type="DFT-s-OFDM",
                        modulation=self.in_modulation,
                        rb_allocation="Inner")
                txpowermax = self.dut.get_rfTxPowerMax(band=self.in_band)

                # Set verdict
                if self.out_EVM_pct <= (target_evm_max - target_evm_margin):
                    self.UpgradeVerdict(OpenTap.Verdict.Pass)
                else:
                    # only set verdict to Fail, if the power is in the acceptable limits considering MPR
                    if self.out_tx_power_dBm<=(txpowermax-txmpr):
                        self.UpgradeVerdict(OpenTap.Verdict.Fail)
                    else:
                        self.log.Debug('Tx Output Power Max exceeded for this signal')

                # ================= Publish Results =======================================
                self.log.Info(f"EVM is {self.out_EVM_pct:.2f}% for {self.out_modulation} for the power level of {self.out_tx_power_dBm:.2f}/{self.out_target_tx_power_dBm:.2f} dBm")
                self.out_modulation = str(modulation)
                self.PublishResult()

        try:
            self.dut.set_rfTxStop()
        except:
            pass

