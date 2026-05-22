"""
U300B0_RFEB_EVT_RX_Gain_Accuracy -- testcase for Rx SNR gain accuracy

Attributes:
    Title:   U300B0_RFEngine_EVT_RX_Gain_Accuracy.py
    Authors: Royal Sethi, Amaury Deplanque, Gernot Hueber
    Copyright: Copyright 2026, Royal Sethi, Gernot Hueber
    License: GPL
    Version: 1.1.0
    Email: gernot.hueber@bc-s.com
"""

__author__ = "Royal Sethi"
__copyright__ = "Copyright 2026, Royal Sethi"
__credits__ = ["Royal Sethi", "Amaury Deplanque", "Gernot Hueber"]
__license__ = "GPL"
__version__ = "1.1.0"
__maintainer__ = "Royal Sethi"
__email__ = "gernot.hueber@umsemi.com"
__status__ = "Production"


import clr
import OpenTap
from opentap import *
from System import Double, String

clr.AddReference("System.Collections")
clr.AddReference("OpenTap.Plugins.BasicSteps")

from opentap import *
from U300_RFEngine.Deembedding import Deembedding
from U300_RFEngine.Testconditions_Limits import Testconditions_Limits
from U300_RFEngine.ThreeGPP.UM_3GPP_5G_NR_Rel_17 import *
from U300_RFEngine.ThreeGPP.UM_3GPP_LTE_Rel_17 import *
from UMT_DUTs.UMT_DUT import UMT_DUT
from UMT_Instruments.SA import SA
from UMT_Instruments.SG import SG

from .U300_RFEngine_EVT_Base import U300_RFEngine_EVT_Base

# Here is how a test step plugin is defined:

#Use the Display attribute to define how the test step should be presented to the user.

@attribute(OpenTap.Display("U300B0_RFEB_EVT_RX_Gain_Accuracy", "RX Gain Accuracy (U300B0-RFE-EVT-002)", "U300B0 RFEngine EVT"))
#AllowAnyChildAttribute is attribute that allows any child step to attached to this step
@attribute(OpenTap.AllowAnyChild())
class U300B0_RFEB_EVT_RX_Gain_Accuracy(U300_RFEngine_EVT_Base): # Inheriting from opentap.TestStep causes it to be a test step plugin.
    # Add properties (name, value, C# type)
    # Metadata information to store
    in_rx_power_backoff_dB = property(Double, 10.0) \
        .add_attribute(OpenTap.Display("set_rx_power_backoff_dB ", "Rx Power Backoff considered between gain and RX power level in dB", "RF Parameters"))\
        .add_attribute(OpenTap.MetaData(True))

    Testcase_ID = property(String, "U300B0-RFE-EVT-002") \
        .add_attribute(OpenTap.Display("Testcase_ID", "Testcase Identifier")) \
        .add_attribute(OpenTap.MetaData(True))

    #INSTRUMENTS
    vsa = property(SA, None)\
        .add_attribute(OpenTap.Display("VSA", "VSA for Rx Measurement", "Instruments"))
    sg = property(SG, None)\
        .add_attribute(OpenTap.Display("SG", "SG For Rx Signal Generation", "Instruments"))
    # DUT
    dut = property(UMT_DUT, None)\
        .add_attribute(OpenTap.Display("DUT", "Any UMT_DUT", "DUT"))

    #output parameters

    out_rx_power_dBm = None
    out_rx_predicted_gain_dB = None
    out_rx_gain_dB = None
    out_rx_gain_delta = None
    out_rfic_gain = None

    rx_gain_table = [61, 58, 55, 52, 49, 46, 43, 40, 37, 34, 30, 27, 24, 21, 18, 15, 12, 9, 6, 3, 0]
    # Use CMW100
    #rx_gain_table = [61, 58, 55, 49, 43, 40, 37, 34, 30, 27, 24, 21]

    def __init__(self):
        super().__init__() # The base class initializer must be invoked.

    def PreRun():
        super().PreRun()
        pass

    def PostRun():
        super().PostRun()

    def Run(self):
        super().Run() ## 3.0: Required for debugging to work.

        # get testcase conditions and limits
        tc_cond_limits = Testconditions_Limits(self.in_conditions_limits_config)
        target_gain_delta = tc_cond_limits.get(self.__class__.__name__, band=self.in_band,
                                            bandwidth_Hz=(self.in_rfbw_Hz), param='GAIN_DELTA')
        if target_gain_delta is None:
            self.log.Error(f"Testconditions and Limits not available for band {self.in_band} in bandwidth {(self.in_rfbw_Hz/1e6)} MHz")

        self.dut.cmd_initialize()
        self.dut.set_rfAssignDlCarriers(self.in_dl_freq_pll_Hz, self.in_band, self.in_rfbw_Hz, self.in_rx_gain_dB,
                                            self.in_freq_offset_dl_Hz,self.in_dl_config, start_rx = False)
        self.dut.set_rfRxStart(self.in_rx_gain_dB,self.in_freq_offset_dl_Hz)

        self.Print_Summary(modulation=self.in_modulation)

        for gain in self.rx_gain_table:
            # read deembedding (loss) data
            deembedding = Deembedding(self.in_deembedding_config)
            deemb_rfeb, deemb_ant, deemb_bb, deemb_coupler = deembedding.get(top='RX', uldl_config=self.in_dl_config_active,
                                                            band=self.in_band, frequency=self.in_dl_freq_pll_Hz)
            if deemb_rfeb is None or deemb_ant is None:
                self.log.Error(f"Deembinding for band {self.in_band} is not defined")

            self.in_rx_gain_dB = gain
            x = self.dut.set_rfRxGain(self.in_rx_gain_dB)
            if self.in_dl_config_active=="RX0_ANT0":
                self.out_rx_predicted_gain_dB = float(x[0])
            elif self.in_dl_config_active=="RX1_ANT1":
                self.out_rx_predicted_gain_dB = float(x[1])
            elif self.in_dl_config_active=="RX1_ANT0":
                self.out_rx_predicted_gain_dB = float(x[1])
            elif self.in_dl_config_active=="RX0_ANT1":
                self.out_rx_predicted_gain_dB = float(x[0])
            else:
                self.out_rx_predicted_gain_dB = float(x[0])

            self.in_rx_level_dBm = -self.out_rx_predicted_gain_dB - self.in_rx_power_backoff_dB     # increase power compensating losses
            #self.out_target_rx_level_dBm = -self.out_target_rx_gain_dB - self.in_cw_backoff_dB

            self.out_rx_level_sg_dBm = self.in_rx_level_dBm - (deemb_rfeb + deemb_ant)

            self.sg.set_arb_signal_rf(signal_type="5G", signal_option=self.in_modulation, frequency_Hz=self.in_dl_freq_pll_Hz,
                                    bw_Hz=self.in_rfbw_Hz, power_level=self.out_rx_level_sg_dBm)

            self.dut.setup_NRRx(sa=self.vsa,in_band=self.in_band, in_freq_pll_Hz=self.in_dl_freq_pll_Hz, in_rfbw_Hz=self.in_rfbw_Hz, scs_Hz=self.in_scs_Hz,
                                in_rb_centre_freq_Hz=self.in_rb_centre_freq_Hz, in_rx_power_dBm=self.in_rx_level_dBm, dl_config_active=self.in_dl_config_active)

            #self.sg.set_rf_power(self.out_rx_level_sg_dBm)
            self.out_rx_power_bb_dBV = self.dut.meas_NrRxPower(sa=self.vsa, in_rfbw_Hz=self.in_rfbw_Hz, scs_Hz=self.in_scs_Hz,
                                                            dl_config_active=self.in_dl_config_active) - deemb_bb

            # if the BB / SI does not respond with a correct value (=None), reboot and skip this iteration
            if self.out_rx_power_bb_dBV is None:
                self.dut.cmd_initialize(force_reboot=True)
                self.dut.set_rfAssignDlCarriers(self.in_dl_freq_pll_Hz, self.in_band, self.in_rfbw_Hz, self.in_rx_gain_dB,
                                                    self.in_freq_offset_dl_Hz,self.in_dl_config, start_rx = False)
                self.dut.set_rfRxStart(self.in_rx_gain_dB,self.in_freq_offset_dl_Hz)
                continue

            self.out_rx_power_bb_dBm = self.vsa.dBV2dBm(self.out_rx_power_bb_dBV)

            self.out_target_rx_level_dBV = self.dut.dBm2dBV(self.in_rx_level_dBm)
            self.out_rx_gain_dB = self.out_rx_power_bb_dBV - self.out_target_rx_level_dBV
            self.out_rx_gain_delta = self.out_rx_gain_dB - self.out_rx_predicted_gain_dB

            self.log.Info(f"Gain Accuracy for {self.in_modulation} for band {self.in_band} is measured: gain error {self.out_rx_gain_delta:.2f} " +
                        f"for measured gain {self.out_rx_gain_dB:.2f} dB and RX Power (ant) of {self.in_rx_level_dBm:.2f} dBm")
            # Set verdict
            if abs(self.out_rx_gain_delta) <= target_gain_delta:
                self.UpgradeVerdict(OpenTap.Verdict.Pass)
            else:
                self.UpgradeVerdict(OpenTap.Verdict.Fail)

            self.PublishResult()

        self.dut.set_rfRxStop()



