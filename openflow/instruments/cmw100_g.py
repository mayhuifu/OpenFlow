"""CMW100GMixin -- generator-side stimulus methods for the R&S CMW100.

Ported from UMT_Instruments/CMW100G.py minus the OpenTAP scaffolding. Only the
methods used by the U300B0 TX EVM Power Sweep demo (set_arb_signal_rf,
set_rf_power) are ported in V1a; other generator methods (set_arb_signal_rf_stop,
set_two_tone_signal_rf, add_blocker_CW) port on demand in V2.
"""
from __future__ import annotations

import logging

from RsCmwGprfGen import *

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

import RsCmwGprfGen.enums as GprfGen_enums


class CMW100GMixin:

    VisaAddress = None
    GprfGen = None
    is_emulation = False

    def __init__(self):
        self.log = logging.getLogger(__name__)
        self.freq_start = 0
        self.freq_stop = 0
        self.err_list = None

    def Open(self, VisaAddress):

        if self.is_emulation:
            return

        self.VisaAddress = VisaAddress
        if self.VisaAddress!=None:
            self.GprfGen = RsCmwGprfGen(self.VisaAddress)
        else:
            self.log.warning("VisaAddress is not defined")

    def Close(self):

        if self.is_emulation:
            return

        self.GprfGen.close()

    #### 5G and 4G functions
    def set_arb_signal_rf(self, signal_type="5G", signal_option="16QAM", frequency_Hz=2.5e6, bw_Hz=10e6,
                        power_level=-35,
                        rf_connector_active=1):

        if self.is_emulation:
            return

        rf_con = GprfGen_enums.TxConnectorBench.R118
        if rf_connector_active == 1:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R11
        elif rf_connector_active == 2:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R12
        elif rf_connector_active == 3:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R13
        elif rf_connector_active == 4:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R14
        elif rf_connector_active == 5:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R15
        elif rf_connector_active == 6:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R16
        elif rf_connector_active == 7:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R17
        elif rf_connector_active == 8:
            rf_con_cmw = GprfGen_enums.TxConnectorCmws.R18

        #self.log.info(f'RF Connector on CMW100G is {rf_connector_active}')

        if signal_type == "CW":
            #self.GprfGen.configure.singleCmw.usage.tx.all.set(rf_con = rf_con, usage = [True, False, False,False,False,False,False,False])
            self.GprfGen.configure.singleCmw.usage.tx.set(tx_connector=rf_con_cmw, usage=True)
            # self.GprfGen.route.scenario.salone.set(tx_connector = GprfGen_enums.TxConnector.I12O, GprfGen_enums = enums.TxConverter.ITX1)
            self.GprfGen.source.rfSettings.set_frequency(frequency_Hz)
            self.GprfGen.source.rfSettings.set_level(power_level)
            self.GprfGen.source.set_bb_mode(baseband_mode = GprfGen_enums.BasebandMode.CW)
            self.GprfGen.source.state.set(True)

        elif signal_type == "5G":
            filename = f"NR_{signal_option}_DL_{(bw_Hz/1e6):g}MHz_Phase_Comp_Off_AB" # NR_16QAM_DL_5MHz_Phase_Comp_OFF_AB
            self.sample_rate = 7680000*(bw_Hz/(5e6))
            if filename is not None:
                path_from = "@WAVEFORM\\"
                file_extension = ".wv"
                file_path = path_from + filename + file_extension
                #self.GprfGen.configure.singleCmw.usage.tx.all.set(rf_con = rf_con, usage = [True, False, False,False,False,False,False,False])
                self.GprfGen.configure.singleCmw.usage.tx.set(tx_connector=rf_con_cmw, usage=True)

                self.GprfGen.source.rfSettings.set_frequency(frequency_Hz)
                self.GprfGen.source.rfSettings.set_level(power_level)
                self.GprfGen.source.set_bb_mode(baseband_mode = GprfGen_enums.BasebandMode.ARB)
                self.GprfGen.source.arb.file.set(arb_file = file_path)
                self.GprfGen.source.state.set(True)

        elif signal_type == "LTE":
            filename = f"LTE_{signal_type}_DL_{(bw_Hz/1e6):g}MHz_Phase_Comp_Off_AB" # NR_16QAM_UL_5MHz_Phase_Comp_OFF_AB
            self.sample_rate = 7680000*(bw_Hz/(5e6))
            if filename is not None:
                path_from = "@WAVEFORM\\"
                file_extension = ".wv"
                file_path = path_from + filename + file_extension
                #self.GprfGen.configure.singleCmw.usage.tx.all.set(rf_con = rf_con, usage = [True, False, False,False,False,False,False,False])
                self.GprfGen.configure.singleCmw.usage.tx.set(tx_connector=rf_con_cmw, usage=True)

                self.GprfGen.source.rfSettings.set_frequency(frequency_Hz)
                self.GprfGen.source.rfSettings.set_level(power_level)
                self.GprfGen.source.set_bb_mode(baseband_mode = GprfGen_enums.BasebandMode.ARB)
                self.GprfGen.source.arb.file.set(arb_file = file_path)
                self.GprfGen.source.state.set(True)
        else:
            self.error="Signal type {signal_type} is not supported"

    def set_rf_power(self, power_in_dBm):

        if self.is_emulation:
            return

        self.GprfGen.source.rfSettings.set_level(power_in_dBm)
        self.GprfGen.source.state.set(True)
