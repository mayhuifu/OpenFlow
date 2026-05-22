"""DUT_FT2232h_V03 — FTDI2232H host-bridge driver for U300 RFIC.

Ported from UMT_DUTs/DUT_FT2232H_V03.py minus OpenTAP scaffolding.
Real hardware path uses pyftdi (SPI over USB); emulation mode bypasses all I/O.
"""
from __future__ import annotations

import copy
import logging
import re
import time

import pandas as pd
from pyftdi.spi import SpiController

from openflow.dut.base import Dut

# Names for Register columns:
    # TODO: This funct is duplicatet in rfic_regmap_module
REG_ADRESS = "Address"
REG_VALUE = "Value"
REG_NAME = "Name"
REG_FIELD_MODE = "Field_Mode"
REG_FIELD_MODE_WRITEABLE = ["RW", "WO"]
REG_FIELD_MODE_READABLE = ["RW", "RO"]
REG_FIELD_MODE_READONLY = ["RO"]

# Set Pins:
DIG_HIGH = 1.8
DIG_LOW = 0

# TODO: This funct is duplicatet in rfic_regmap_module
class Register():
    """ Class combining the values for one register """
    def __init__(self, adr, val, name, field_mode):
        self.adr = int(adr)
        if val.is_integer():
            # a reasonable integer-like value is given
            self.val = int(val)
        elif field_mode is REG_FIELD_MODE_WRITEABLE:  # the field mode is actually writeable --> raise an issue!
            # not a proper integer, but also the value should be written at some point --> ERROR
            raise ValueError("No proper value specified for reg adress %d - and it is not a read-only field" %self.adr)
        else:
            # not a proper integer, but should also not be written (i.e. read-only, e.g. float('nan'))
            self.val = val

        self.name = str(name)
        self.field_mode = str(field_mode)

    def export_dict(self):
        return {REG_ADRESS: self.adr,
                REG_VALUE: self.val,
                REG_NAME:self.name,
                REG_FIELD_MODE: self.field_mode}



class DUT_FT2232h_V03(Dut):
    '''wrapper for r/w functions using the FT2232H on the Sandrine Host board,
    Pin configurations:
        CLK = RXA_PWR
        SDA = RXB_PWR
        SDO = RXC_PWR
        CS = RXD_PWR
    '''

    # General Settings for the FTDI:
    adress: str = "ftdi://ftdi:2232h:ASK-22-17-3126/2"
    emulation: bool = False

    chip_id: str = ""
    reg_map_file: str = "U300_RFIC_A0_V00.csv"

    nCS: int = 2
    select_cs: int = 0
    mode: int = 0
    freq: float = 200E3

    # # ============== Instruments ===============================
    psu_supply_RFIC = None

    psu_supply_BUFFERS = None

    psu_pins = None

    # # ============== Inputs ====================================  #TODO: Maybe disable them
    in_voltage_supply1V4_V: float = 1.4
    ch_voltage_supply1V4_: int = 1

    in_voltage_supply1V8_V: float = 1.8
    ch_voltage_supply1V8_: int = 2

    in_voltage_supply2V5_V: float = 2.5
    ch_voltage_supply2V5_: int = 3

    in_voltage_buffer1V35_V: float = 1.35
    ch_voltage_buffer1V35_: int = 1

    in_voltage_buffer0V4_V: float = 0.4
    ch_voltage_buffer0V4_: int = 1

    in_voltage_buffer5V_V: float = 5
    ch_voltage_buffer5V_: int = 2

    in_voltage_bufferN5V_V: float = -5.0
    ch_voltage_bufferN5V_: int = 3

    ch_voltage_RESETN_: int = 2

    ch_voltage_CIFPMUEN_: int = 1

    def __init__(self):
        super().__init__()  # The base class initializer must be invoked.
        self.log = logging.getLogger(__name__)
        self.Name = "DUT_FT2232h_V03"
        self.reg_cached = None
        self.reg_read = None


    def Open(self):
        """Called by TAP when the test plan starts."""
        # emulation mode:
        if self.emulation:
            self.log.info("DUT in Emulation mode")
            self.port = None
            self.ctrl = None
        else:
            self.psu_supply_RFIC.cmd_reset()

            # # Set all Buffer powersupplies
            # turn on VDD Buffer +-5V:
            self.psu_supply_BUFFERS.cmd_reset()
            self.psu_supply_BUFFERS.set_voltage_setpoint(self.ch_voltage_buffer5V_, self.in_voltage_buffer5V_V)
            self.psu_supply_BUFFERS.set_current_limit(self.ch_voltage_buffer5V_, 0.5)

            self.psu_supply_BUFFERS.set_voltage_setpoint(self.ch_voltage_bufferN5V_, self.in_voltage_bufferN5V_V)
            self.psu_supply_BUFFERS.set_current_limit(self.ch_voltage_bufferN5V_, 0.5)

            self.psu_supply_BUFFERS.set_output_enabled(True)            #enables all output on the supply_buffer

            # # Set all rfic powersupplies:
            # supply for 1.4V and 1.8V  RFIC
            self.psu_supply_RFIC.set_voltage_setpoint(self.ch_voltage_supply1V4_, self.in_voltage_supply1V4_V)
            self.psu_supply_RFIC.set_current_limit(self.ch_voltage_supply1V4_, 0.1)     #TODO: check if to low
            self.psu_supply_RFIC.set_voltage_setpoint(self.ch_voltage_supply1V8_, self.in_voltage_supply1V8_V)
            self.psu_supply_RFIC.set_current_limit(self.ch_voltage_supply1V8_, 0.1)     #TODO: check if to low
            # supply for 2.5V RFIC
            self.psu_supply_RFIC.set_voltage_setpoint(self.ch_voltage_supply2V5_, self.in_voltage_supply2V5_V)
            self.psu_supply_RFIC.set_current_limit(self.ch_voltage_supply2V5_, 0.1)     #TODO: check if to low
            #they are enabled in the base class

            # configure the reset PSU:
            self.psu_pins.set_voltage_setpoint(self.ch_voltage_RESETN_, DIG_LOW)
            self.psu_pins.set_current_limit(self.ch_voltage_RESETN_, 0.01)
            self.psu_pins.set_voltage_setpoint(self.ch_voltage_CIFPMUEN_, DIG_LOW)
            self.psu_pins.set_current_limit(self.ch_voltage_CIFPMUEN_, 0.01)
            self.psu_pins.set_output_enabled(False)
            time.sleep(1)
            self.psu_pins.set_output_enabled(True)
            # some time to settle:
            time.sleep(2)

            # write here your opening command:
            #FIXME: This SPI implementation cannot by used by the Sandrin board!
            self.ctrl = SpiController(self.nCS) # SpiController(cs_count=self.nCS)
            self.ctrl.configure(self.adress) # configure(self.adress)
            self.port = self.ctrl.get_port(self.select_cs, freq=self.freq, mode=self.mode)
            self.log.info(self.Name + " Opened")
            self.log.warning("This SPI configuration does not work with the Sandrin board. SDI and CS pins are wrong!!")

    def Close(self):
        """Called by TAP when the test plan ends."""
        self.log.info(self.Name + " Closed")
        self.psu_supply_BUFFERS.Close()
        self.psu_pins.Close()

    # # ========================= PSU Control functions ================================= # #
    def set_buffer_rx_supply(self):
        self.psu_supply_BUFFERS.set_voltage_setpoint(self.ch_voltage_buffer0V4_, self.in_voltage_buffer0V4_V)
        self.psu_supply_RFIC.set_current_limit(self.ch_voltage_buffer0V4_, 0.4)             #TODO: check if to low
        self.psu_supply_BUFFERS.set_output_enabled(True, self.ch_voltage_buffer0V4_)

    def set_output_enabled_RFIC_1V4(self, state):
        self.psu_supply_RFIC.set_output_enabled(state, self.ch_voltage_supply1V4_)

    def set_output_enabled_RFIC_1V8(self, state):
        self.psu_supply_RFIC.set_output_enabled(state, self.ch_voltage_supply1V8_)

    def set_output_enabled_RFIC_2V5(self, state):
        self.psu_supply_RFIC.set_output_enabled(state, self.ch_voltage_supply2V5_)

    # # ====================== RESETN and CIFPMUEN Pin functions ===================== # #
    def set_RESETN(self, is_on):
        """ Turns on / off the RESETN Pin"""
        if is_on:
            val = DIG_HIGH
        else:
            val = DIG_LOW

        self.psu_pins.set_voltage_setpoint(self.ch_voltage_RESETN_, val)

    def trigger_APLL(self):
        """ Triggers the APLL Pin """
        self.log.error("TODO: Implement the trigger for the APLL Pin!!")

    def set_CIFPMUEN(self, is_on):
        """ Turns on /off the CIFPMUEN Pin"""
        if is_on:
            val = DIG_HIGH
        else:
            val = DIG_LOW

        self.psu_pins.set_voltage_setpoint(self.ch_voltage_CIFPMUEN_, val)

   # # ========Functions for SPI communications============================================ # #

    #FIXME: does not work with Sandrin board!!!
    def _create_spi_write_cmd(self, val_list):
        """creates a valid spi write command from an integer list. Each int is represented by 2 bytes """
        r_val = [] # a list of all byte-sized values in val_list

        # for each value:
        for val in val_list:
            if val > 0xffff:
                raise ValueError("values larger than 2 bytes not supported!")

            # split in msb and lsb
            msb = val & 0xff00
            msb = msb >> 8
            lsb = val & 0x00ff

            # append to list:
            r_val.append(msb)
            r_val.append(lsb)

        return bytearray(r_val)
    #FIXME: does not work with Sandrin board!!!
    def _convert_spi_read_values(self, b_array, word_size_in_bytes=2):
        """ Takes the returned bytearray and converts it in 16bit integers
        b_array: bytearray(b'\x01\x01\x10\0x10')

        returns [257, 4112] """

        r_val = []
        for i in range(0, len(b_array)):
            if i%word_size_in_bytes == 0:
                msb = b_array[i]
                lsb = b_array[i+1]

                val = msb << 8
                val = val + lsb

                r_val.append(val)
        return r_val

    def read_chip_id(self):
        """ reads the Chip ID from the RFIC """
        self.log.warning("read_chip_id() not implemented")
        self.chip_id = "NOT IMPLEMENTED"


    def load_reg_map(self, reg_map_file):
        """ loads the defined register map into an internal buffer """
        self.reg_map_file = reg_map_file
        df = pd.read_csv(self.reg_map_file)

        self.reg_cached = []

        for index, row in df.iterrows():
            self.reg_cached.append(Register(
                row[REG_ADRESS],
                row[REG_VALUE],
                row[REG_NAME],
                row[REG_FIELD_MODE]))

    def save_reg_map(self, filename):
        """ Saves all read falues to a .csv file """
        # get the current path to the reg-file:
        self.log.info("Saving read-register map to %s"%filename)
        df = self._create_new_dataframe()
        self._add_reg_list_to_dataframe(df, self.reg_read)
        df.to_csv(filename, index=False)

    # TODO: This funct is duplicatet in rfic_regmap_module
    def _create_new_dataframe(self):
        """ creates out of the register list a pandas data frame """

        # create column header:
        reg0 = Register(0,0,0,0)
        reg0_export = reg0.export_dict()
        columns = reg0_export.keys()

        # create dataframe
        df = pd.DataFrame(columns=columns)

        return df

    # TODO: This funct is duplicatet in rfic_regmap_module
    def _add_reg_list_to_dataframe(self, df, reg_list):
        """ adds all values from reg_list to dataframe"""

        # add each data line:
        for reg in reg_list:
            df.loc[len(df)] = reg.export_dict()
        return # no return needed, as df is updated

    #FIXME: does not work with Sandrin board!!!
    def read(self, adr, nWords=1, word_size_in_bytes=2, emulation_return=0x0000):
        """ SPI write """
        # handle emulation mode
        if self.emulation:
            self.log.info("Emulation: Read %d bytes from adr %d, "%(nWords, adr))
            return emulation_return

        # real-world mode:
        self.log.debug("%s: Read %d words from adr %d, "%(self.Name, nWords, adr))
        spi_seq = self._create_spi_write_cmd([adr])
        read_buf = self.port.exchange(spi_seq, readlen=nWords*word_size_in_bytes) # the query
        int_list = self._convert_spi_read_values(read_buf, word_size_in_bytes=word_size_in_bytes)

        if nWords == 1:
            # only return 1 value, not a list:
            int_list = int_list[0]
        return int_list

    #FIXME: does not work with Sandrin board!!!
    def write(self, adr, val):
        """ SPI write """
        # handle emulation mode
        if self.emulation:
            self.log.info("Emulation: Write to %d val %d"%(adr, val))
            return

        # real-world mode:
        self.log.debug("%s: Write to %d, value %d"%(self.Name, adr, val))
        spi_seq = self._create_spi_write_cmd([adr, val])  # construct a bytearray
        read_buf = self.port.exchange(spi_seq, duplex=True)
        return
#FIXME: does not work with Sandrin board!!!
    def spi_block_write_write(self, adress_mask_value, spi_block_string):
        """ Takes a string with multiple spi_write(val|mask, 16h'xxxx) and writes each spi-command.
        e.g.
        # # 	spi_write(106|w_rx_addr_mask,16'h38E3);
        # # 	spi_write(107|w_rx_addr_mask,16'h3F0E);
        # # 	spi_write(108|w_rx_addr_mask,16'h0E90); //RXPMUBGENCP
        # # 	spi_write(109|w_rx_addr_mask,16'h403C);
        # # 	spi_write(6|w_rx_addr_mask,16'h7DF0);
        """

        all_occurences = re.findall(r"spi_write\((.*),(.*)\)", spi_block_string)   # explnation: regular expression searches for all occurances with "spi_write(xxx)", and returns all values inside the brackets (specified with .*)
        # the backslashes in \( and \) are needed to escape the special characters of the regex, otherwise ith would return them aswell.
        # the inner brackets specify to return only what is inside the inner brackets
        # the 'r' at the beginning is needed to escape the special character '\' in python strings

        self.log.debug("Found %d spi_write commands in the given string."%len(all_occurences))
        for occ in all_occurences:
            adr_expr = occ[0]
            val_expr = occ[1]

            # convert the write-address expression from '10|mask_name' to int:
            adr_offset_str_list = re.findall(r"(.*)\|.*", adr_expr)  # returns from 10|mask_name_rx only ['10']
            if not len(adr_offset_str_list) == 1:
                raise ValueError("Error in reg-expr of spi-block :" + spi_block_string)
            adr_without_mask = int(adr_offset_str_list[0])  # only one occurence found, get that occurance and convert to int:
            adr = adr_without_mask | adress_mask_value  # add the mask for the values

            # convert the write-value from the 16'hFFFF format to integer:
            val_hex_str_list = re.findall("16'h(.*)", val_expr)  # converts from "16hxxxx" to "xxxx"
            if not len(val_hex_str_list) == 1:
                raise ValueError("Error in reg-expr of spi-block :" + spi_block_string)
            val = int(val_hex_str_list[0], 16)  # convert the hex number "xxxx" to integer

            # now conversion is done:
            self.write(adr, val)

#FIXME: does not work with Sandrin board!!!
    def write_all(self):
        """ Writes all values from a list of registers """
        self.log.debug("Writing all (%d) Registers from cached values"% len(self.reg_cached))
        for reg in self.reg_cached:
            # check if value can be written
            if reg.field_mode in REG_FIELD_MODE_WRITEABLE:
                self.write(reg.adr, reg.val)
                time.sleep(0.03)
        self.log.debug("Writing (%d) Registers DONE"% len(self.reg_cached))

#FIXME: does not work with Sandrin board!!!
    def read_all(self):
        """ Reads all register-addresses specified in self.reg_cached """
        self.log.debug("Reading all (%d) Registers from cached values"% len(self.reg_cached))
        self.reg_read = []
        for reg in self.reg_cached:
            # check if value can be read
            if reg.field_mode in REG_FIELD_MODE_READABLE:
                val = self.read(reg.adr)
                time.sleep(0.03)
                reg_read = copy.copy(reg)
                reg_read.val = val
                self.reg_read.append(reg_read)
        self.log.debug("Reading (%d) Registers DONE"% len(self.reg_cached))
