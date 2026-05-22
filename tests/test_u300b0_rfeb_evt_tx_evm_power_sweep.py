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
import math
import time

import numpy as np
from openflow.rfengine.calibration_file import Calibration_File
from openflow.rfengine.deembedding import Deembedding
from openflow.rfengine.testconditions_limits import Testconditions_Limits
from openflow.dut.base import Dut  # DUT for SPI Write
from openflow.instruments.cmw100 import CMW100
from openflow.instruments.stubs import DMM
from openflow.instruments.stubs import WFG
import logging
logger = logging.getLogger(__name__)
TESTCASE_ID = "U300B0-RFE-EVT-005"
def test_u300b0_rfeb_evt_tx_evm_power_sweep(cmw100, wfg, dut, dmm_c, dmm_v, config, results):

    Setup_DMM()

    # get testcase conditions and limits
    tc_cond_limits = Testconditions_Limits(config.conditions_limits_config)
    target_tx_power = config.tx_power_dBm

    # read deembedding (loss) data
    deembedding = Deembedding(config.deembedding_config)
    deemb_rfeb, deemb_ant, deemb_bb, deemb_coupler = deembedding.get(top='TX', uldl_config=config.ul_config,
                                                    band=config.band, frequency=config.ul_freq_pll_Hz)
    if deemb_rfeb is None or \
            deemb_ant is None or \
            deemb_bb is None:
        logger.error("Deembedding data cannot be read")
        return

    # get calibration file data
    cal_file = Calibration_File(config.calibration_file_config, config.rfeb_sn, config.rfhb_sn)
    i_offset_A, q_offset_A = cal_file.get_iq_dc_offset(config.band_num=dut.get_BandNumber(config.band), config.rfbw_Hz=config.rfbw_Hz)
    iq_gain_imbalance_dB, iq_phase_imbalance_deg = cal_file.get_iq_gain_phase_imbalance(dut.get_BandNumber(config.band), config.rfbw_Hz)

    # setup RFIC+RFFE
    pwr, backoff = initialize_tx(target_tx_power=target_tx_power)

    #
    # TESTCASE DESCRIPTION
    #
    # - Supply RFIC (1.4V, 1.8V, 2.5V, CIFPMUEN=high, nRST=low); |br| write/read full register map, then put RFIC into reset & CIFPMUEN=off continuously for 24hrs; |br| capture number of data errors

    #for modulation in ["QPSK", "16QAM", "64QAM", "256QAM"]:
    for modulation in ["16QAM"]:

        target_evm_max = tc_cond_limits.get_band_modulation(__class__.__name__, band=config.band,
                                        modulation=modulation, param = 'EVM_MAX')
        target_evm_margin = tc_cond_limits.get_band_modulation(__class__.__name__, band=config.band,
                                        modulation=modulation, param='EVM_MAX_margin')
        # configure and enable waveform generator
        try:
            dut.set_arb_signal_bb(wfg=wfg, signal_type="5G", signal_option=config.modulation, bw_Hz=config.rfbw_Hz,
                    power_dBFSrms=-backoff, deembedding=deemb_bb,
                    i_offset_A=i_offset_A, q_offset_A=q_offset_A,
                    iq_gain_imbalance_dB=iq_gain_imbalance_dB, iq_phase_imbalance_deg=iq_phase_imbalance_deg,
                    ul_frequency_Hz=config.ul_freq_pll_Hz, scs_Hz=config.scs_Hz,
                    band=config.band)
        except Exception:
                logger.warning("Unable to set BB signal, restart BB/RFIC")
                pwr, backoff = initialize_tx(target_tx_power=target_tx_power, force_reboot=True)

        Print_Summary(modulation=modulation)

        for target_tx_power in np.arange(-45, 28+1, 1.0):

            try:
                # first reduce the power from the WFG to a low value
                dut.set_arb_power_dBFSrms(wfg=wfg, power_dBFSrms=-30, deembedding=deemb_bb,
                            i_offset_A=i_offset_A, q_offset_A=q_offset_A,
                            iq_gain_imbalance_dB=iq_gain_imbalance_dB, iq_phase_imbalance_deg=iq_phase_imbalance_deg,
                            scs_Hz=config.scs_Hz, rfbw_Hz=config.rfbw_Hz, ul_frequency_Hz=config.ul_freq_pll_Hz,
                            band=config.band)

                pwr, out_tx_rfic_lut_idx, out_tx_pa_lut_idx, dac_bo = dut.set_rfTxPower(target_tx_power, config.tx_power_backoff_dB, config.rb_centre_freq_Hz,
                                                                    config.ul_freq_pll_Hz, backoff_mode="auto",
                                                                        antenna_config=config.ul_config, scs_Hz=config.scs_Hz)
                backoff = (pwr-target_tx_power+config.tx_dac_backoff_dBFS)  # backoff: target versus what the RFIC+RFFE can achieve
                dut.set_arb_power_dBFSrms(wfg=wfg, power_dBFSrms=-backoff, deembedding=deemb_bb,
                            i_offset_A=i_offset_A, q_offset_A=q_offset_A,
                            iq_gain_imbalance_dB=iq_gain_imbalance_dB, iq_phase_imbalance_deg=iq_phase_imbalance_deg,
                            scs_Hz=config.scs_Hz, rfbw_Hz=config.rfbw_Hz, ul_frequency_Hz=config.ul_freq_pll_Hz,
                            band=config.band)
            except Exception:
                logger.warning("Unable to set BB signal, restart BB/RFIC")
                pwr, backoff = initialize_tx(target_tx_power=target_tx_power, force_reboot=True)
                if pwr < -100:
                    return
                continue

            # read measurement from CMW100
            if config.board_config=="RFEB1":
                fe_gain_offset_dB = 0
            elif (config.board_config=="RFPB") & (target_tx_power<-4):
                fe_gain_offset_dB = -12
            elif (config.board_config=="RFPB") & (target_tx_power>=-4):
                fe_gain_offset_dB = -24
            else:
                fe_gain_offset_dB = 0
            cmw100.setup_NrTx(config.band=config.band, config.freq_pll_Hz=config.ul_freq_pll_Hz,
                                config.rfbw_Hz=config.rfbw_Hz, config.tx_power_dBm=target_tx_power+fe_gain_offset_dB,
                                config.modulation=modulation, config.ul_config=config.ul_config, config.scs_Hz=config.scs_Hz)

            cmw100.meas_NrTxAll()
            tx_power = cmw100.meas_NrTxPower(use_cached=True)

            if math.isnan(tx_power):
                logger.warning("CMW unable to report Tx Power level")
                time.sleep(1)
                continue

            out_EVM_pct = cmw100.meas_NrTxEVM(use_cached=True)
            if math.isnan(out_EVM_pct):
                logger.warning("CMW unable to report Tx EVM")
                time.sleep(1)
                continue

            # compensate the measured power with the deembedding (losses)
            # and calculate the accurate (deviation from target)
            out_tx_power_dBm = tx_power - deemb_rfeb - deemb_ant
            out_target_tx_power_dBm = target_tx_power
            out_modulation = modulation
            out_tx_power_rfd_dBm = pwr
            out_tx_backoff_dB = backoff
            Get_Aux()
            Get_DMM()

            # Set verdict
            txmpr = dut.get_rfTxMPR(band=config.band, ofdm_type="DFT-s-OFDM",
                    modulation=config.modulation,
                    rb_allocation="Inner")
            txpowermax = dut.get_rfTxPowerMax(band=config.band)

            # Set verdict
            if out_EVM_pct <= (target_evm_max - target_evm_margin):
                pass
            else:
                # only set verdict to Fail, if the power is in the acceptable limits considering MPR
                if out_tx_power_dBm<=(txpowermax-txmpr):
                    assert False, "verdict Fail"
                else:
                    logger.debug('Tx Output Power Max exceeded for this signal')

            # ================= Publish Results =======================================
            logger.info(f"EVM is {out_EVM_pct:.2f}% for {out_modulation} for the power level of {out_tx_power_dBm:.2f}/{out_target_tx_power_dBm:.2f} dBm")
            out_modulation = str(modulation)
            results.publish(out_tx_rfic_lut_idx=out_tx_rfic_lut_idx, out_tx_pa_lut_idx=out_tx_pa_lut_idx, out_EVM_pct=out_EVM_pct, out_tx_power_dBm=out_tx_power_dBm, out_target_tx_power_dBm=out_target_tx_power_dBm, out_modulation=out_modulation, out_tx_power_rfd_dBm=out_tx_power_rfd_dBm, out_tx_backoff_dB=out_tx_backoff_dB)  # TODO[openflow-migrate]: choose which out_* values to publish

    try:
        dut.set_rfTxStop()
    except Exception:
        pass

