"""Library for reading and writing calibration files.

Ported from ``U300_RFEngine/Calibration_File.py`` minus the OpenTAP
scaffolding. Specifically:

* The original ``import clr``/``clr.AddReference("OpenTap")``/``import
  OpenTap``/``import opentap`` block is dropped.
* The base class ``OpenTap.Resource`` is replaced with the implicit
  ``object`` base — the OpenTAP resource lifecycle was never used by the
  calibration data path.

Everything else (YAML round-tripping, nested-dict get/set helpers, the
TX/RX cal-data builders, and the convenience accessors used by the TX EVM
test plan) is preserved bit-for-bit.
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

import yaml


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


RF_ID_PLACEHOLDER = "<RF_ID>"
BB_ID_PLACEHOLDER = "<BB_ID>"


class Calibration_File:
    def __init__(self, filename, rf_sn="", bb_sn=""):
        self.log = logging.getLogger(__name__)
        self.filename = (
            filename.replace(RF_ID_PLACEHOLDER, "_" + rf_sn)
            .replace(BB_ID_PLACEHOLDER, "_" + bb_sn)
            .replace(" ", "_")
        )
        self.err = ""

        try:
            with open(self.filename, "r") as f:
                try:
                    self.config = yaml.load(f, Loader=yaml.FullLoader)
                    if self.config is None:
                        self.config = dict()
                except Exception:
                    self.err = (
                        f"Calibration_File: Could not load File {filename}. "
                        "Potential file corruption."
                    )
                    self.filename = self.filename + "_1"
                    self.config = dict()
        except Exception:
            self.err = f"Calibration_File: Could not load File {filename}."
            self.config = dict()

    def save(
        self,
        room_temp_C10=250,
        temp_rfic_C10=None,
        temp_sensor0_C10=None,
        temp_sensor1_C10=None,
        temp_fem_C10=None,
    ):
        self.set("general", "calibration_file_version", "v0.2.0")
        self.set("general", "calibration_date", str(datetime.date.today()))
        self.set(
            "general",
            "calibration_time",
            str(datetime.datetime.now().strftime("%H:%M:%S")),
        )
        self.set("general", "calibration_temperature_room", round(room_temp_C10 * 10))
        if temp_rfic_C10 is not None:
            self.set(
                "general", "calibration_temperature_rfic", round(temp_rfic_C10 * 10)
            )
        if temp_sensor0_C10 is not None:
            self.set(
                "general",
                "calibration_temperature_sensor0",
                round(temp_sensor0_C10 * 10),
            )
        if temp_sensor1_C10 is not None:
            self.set(
                "general",
                "calibration_temperature_sensor1",
                round(temp_sensor1_C10 * 10),
            )
        if temp_fem_C10 is not None:
            self.set(
                "general", "calibration_temperature_fem", round(temp_fem_C10 * 10)
            )
        self.set("general", "calibration_tool", 0)
        self.set("general", "calibration_tool_version", "v2.2.2")
        try:
            with open(self.filename, "w") as f:
                yaml.dump(
                    self.config, f, Dumper=NoAliasDumper, sort_keys=False, indent=2
                )
        except Exception as e:
            self.err = (
                f"Calibration_File: Could not store File {self.filename}. "
                f"Reason: {e}"
            )

    def get(self, cal_group, param):
        try:
            r = self.config[cal_group][param]
            return r
        except Exception:
            return 0

    def set(self, cal_group, param, value):
        try:
            if self.config.get(cal_group) is not None:  # check if is there
                self.config[cal_group][param] = value
            else:
                self.config[cal_group] = dict()
                self.config[cal_group][param] = value
        except Exception:
            pass

    def get_band_bandwidth(self, cal_group, band, bandwidth_Hz, param):
        bw = str(f"{bandwidth_Hz/1e6:g}")
        try:
            r = self.config[cal_group][band][bw][param]
            return r
        except Exception:
            return 0

    def set_band_bandwidth(self, cal_group, band, bandwidth_Hz, param, value):
        bw = str(f"{bandwidth_Hz/1e6:g}")
        try:
            if self.config.get(cal_group) is not None:
                if self.config[cal_group].get(band) is not None:
                    if self.config[cal_group][band].get(bw) is not None:
                        self.config[cal_group][band][bw][param] = value
                    else:
                        self.config[cal_group][band][bw] = dict()
                        self.config[cal_group][band][bw][param] = value
                else:
                    self.config[cal_group][band] = dict()
                    self.config[cal_group][band][bw] = dict()
                    self.config[cal_group][band][bw][param] = value
            else:
                self.config[cal_group] = dict()
                self.config[cal_group][band] = dict()
                self.config[cal_group][band][bw] = dict()
                self.config[cal_group][band][bw][param] = value
        except Exception:
            pass

    def get_band_ant_bandwidth(self, cal_group, band, ant, bandwidth_Hz, param):
        bw = str(f"{bandwidth_Hz/1e6:g}")
        try:
            r = self.config[cal_group][band][ant][bw][param]
            return r
        except Exception:
            return 0

    def set_band_ant_bandwidth(self, cal_group, band, ant, bandwidth_Hz, param, value):
        bw = str(f"{bandwidth_Hz/1e6:g}")
        try:
            if self.config.get(cal_group) is not None:
                if self.config[cal_group].get(band) is not None:
                    if self.config[cal_group][band].get(ant) is not None:
                        if self.config[cal_group][band][ant].get(bw) is not None:
                            self.config[cal_group][band][ant][bw][param] = value
                        else:  # no leaf for <bw>
                            self.config[cal_group][band][ant][bw] = dict()
                            self.config[cal_group][band][ant][bw][param] = value
                    else:  # no leaf for <ant>
                        self.config[cal_group][band][ant] = dict()
                        self.config[cal_group][band][ant][bw] = dict()
                        self.config[cal_group][band][ant][bw][param] = value
                else:  # no leaf for <band>
                    self.config[cal_group][band] = dict()
                    self.config[cal_group][band][ant] = dict()
                    self.config[cal_group][band][ant][bw] = dict()
                    self.config[cal_group][band][ant][bw][param] = value
            else:  # no leaf for <cal_group>
                self.config[cal_group] = dict()
                self.config[cal_group][band] = dict()
                self.config[cal_group][band][ant] = dict()
                self.config[cal_group][band][ant][bw] = dict()
                self.config[cal_group][band][ant][bw][param] = value
        except Exception:
            pass

    def set_gain_iq_dac_lsb(self, i_dac_lsb, q_dac_lsb, gain_values):
        gain_entries = []
        for idx, gain in enumerate(gain_values):
            i_val = i_dac_lsb[idx] if idx < len(i_dac_lsb) else 0
            q_val = q_dac_lsb[idx] if idx < len(q_dac_lsb) else 0
            gain_entries.append(
                {
                    "gain_100dB": gain,
                    "i_dac_lsb": i_val,
                    "q_dac_lsb": q_val,
                }
            )
        return gain_entries

    def set_iq_dac_lsb(
        self, bw_list, iq_dac_lsb_freq, i_dac_lsb, q_dac_lsb, gain_values
    ):
        """Builds the i_q_dc_imbalance structure for a band.

        Args:
            bw_list (list[int]): Bandwidths in MHz (e.g., [5, 10, 20])
            iq_dac_lsb_freq (list[float]): Frequencies in MHz (e.g., [0.0, 1.0])
            i_dac_lsb (list[int]): I DAC values
            q_dac_lsb (list[int]): Q DAC values
            gain_values (list[int]): gain_100dB values

        Returns:
            list[dict]: per_bw structure for YAML output
        """
        iq_dac_lsb_freq_khz = [int(freq / 1e3) for freq in iq_dac_lsb_freq]
        gain_entries = self.set_gain_iq_dac_lsb(i_dac_lsb, q_dac_lsb, gain_values)

        per_bw_entries = []
        for bw_mhz in bw_list:
            per_freq_entries = []
            for freq_khz in iq_dac_lsb_freq_khz:
                per_freq_entries.append(
                    {
                        "freq_khz": freq_khz,
                        "per_gain": gain_entries,
                    }
                )
            per_bw_entries.append(
                {
                    "bw_mhz": bw_mhz,
                    "per_freq": per_freq_entries,
                }
            )
        return per_bw_entries

    def set_rx_rf_cal_data(
        self,
        band: int,
        freqs: list[int],
        bws_hz: list[int],
        freq_gain_offsets: list[int] = None,
        gain_offsets_elna: list[int] = None,
        bw_gain_offsets: list[int] = None,
        iq_dac_lsb_freq: list[float] = None,
        gain_values: list[int] = None,
        i_dac_lsb: list[int] = None,
        q_dac_lsb: list[int] = None,
        rx_ant_routings: list[int] = None,
    ):
        in_bw_mhz = [int(bw_hz / 1e6) for bw_hz in bws_hz]

        if freq_gain_offsets is not None:
            per_freq_entries = [
                {"freq_khz": int(f / 1e3), "gain_offset": g}
                for f, g in zip(freqs, freq_gain_offsets, strict=False)
            ]

        if bw_gain_offsets is not None:
            per_bw_entries = [
                {"bw_mhz": bw, "gain_offset": g}
                for bw, g in zip(in_bw_mhz, bw_gain_offsets, strict=False)
            ]

        im2_dac_codes = None
        if (
            iq_dac_lsb_freq is not None
            and gain_values is not None
            and i_dac_lsb is not None
            and q_dac_lsb is not None
        ):
            in_bw_mhz = [int(bw_hz / 1e6) for bw_hz in bws_hz]
            im2_dac_codes = self.set_iq_dac_lsb(
                in_bw_mhz,
                iq_dac_lsb_freq,
                i_dac_lsb,
                q_dac_lsb,
                gain_values,
            )

        rx_ant_routings_cal_data = []
        rx_cal_data_routings = []

        for idx in rx_ant_routings:
            rx_ant_routings_cal_data.append(idx)
            offsets = {}
            if freq_gain_offsets is not None:
                offsets["per_freq"] = per_freq_entries
            if gain_offsets_elna is not None:
                if len(gain_offsets_elna) != 2:
                    raise ValueError(
                        "gain_offsets_elna must have exactly 2 values: [off, high]"
                    )
                offsets["gain_offset_elna"] = {
                    "high": gain_offsets_elna[0],
                    "off": gain_offsets_elna[1],
                }
            if bw_gain_offsets is not None:
                offsets["per_bw"] = per_bw_entries

            im2_dict = {}
            if im2_dac_codes is not None:
                im2_dict["per_bw"] = im2_dac_codes

            rx_cal_data_routings.append(
                {
                    "offsets": offsets,
                    "im2_dac_codes": im2_dict,
                }
            )

        data_rx = {
            "band": band,
            "rx_ant_routings": {
                "ant_routings": rx_ant_routings_cal_data,
                "rx_cal_data": rx_cal_data_routings,
            },
        }

        if "rx_carriers" not in self.config or not isinstance(
            self.config["rx_carriers"], list
        ):
            self.config["rx_carriers"] = []

        rx_carriers = self.config["rx_carriers"]
        updated_rx = False
        for i, entry in enumerate(rx_carriers):
            if entry.get("band") == band:
                existing_routings = entry["rx_ant_routings"]["ant_routings"]
                existing_cal_data = entry["rx_ant_routings"]["rx_cal_data"]

                for idx, ant in enumerate(rx_ant_routings):
                    if ant in existing_routings:
                        ant_idx = existing_routings.index(ant)
                        existing_entry = existing_cal_data[ant_idx]
                        new_entry = rx_cal_data_routings[idx]

                        # --- Merge 'per_bw' in offsets ---
                        if bw_gain_offsets is not None:
                            existing_bw = {
                                bw_entry["bw_mhz"]: bw_entry
                                for bw_entry in existing_entry["offsets"]["per_bw"]
                            }
                            for new_bw_entry in new_entry["offsets"]["per_bw"]:
                                existing_bw[new_bw_entry["bw_mhz"]] = new_bw_entry
                            existing_entry["offsets"]["per_bw"] = list(
                                existing_bw.values()
                            )

                        # --- Merge 'per_freq' in offsets only if freq_gain_offsets is provided ---
                        if freq_gain_offsets is not None:
                            existing_entry["offsets"]["per_freq"] = new_entry[
                                "offsets"
                            ]["per_freq"]

                        # --- Replace 'gain_offset_elna' only if gain_offsets_elna is provided ---
                        if gain_offsets_elna is not None:
                            existing_entry["offsets"]["gain_offset_elna"] = {
                                "high": gain_offsets_elna[0],
                                "off": gain_offsets_elna[1],
                            }

                        if (
                            "im2_dac_codes" in new_entry
                            and "per_bw" in new_entry["im2_dac_codes"]
                            and new_entry["im2_dac_codes"]["per_bw"] is not None
                        ):
                            existing_im2 = {}
                            if (
                                "im2_dac_codes" in existing_entry
                                and "per_bw" in existing_entry["im2_dac_codes"]
                            ):
                                existing_im2 = {
                                    bw_entry["bw_mhz"]: bw_entry
                                    for bw_entry in existing_entry["im2_dac_codes"][
                                        "per_bw"
                                    ]
                                }
                            for new_im2_entry in new_entry["im2_dac_codes"]["per_bw"]:
                                existing_im2[new_im2_entry["bw_mhz"]] = new_im2_entry

                            if "im2_dac_codes" not in existing_entry:
                                existing_entry["im2_dac_codes"] = {}
                            existing_entry["im2_dac_codes"]["per_bw"] = list(
                                existing_im2.values()
                            )

                    else:
                        # New antenna: add it completely
                        existing_routings.append(ant)
                        existing_cal_data.append(rx_cal_data_routings[idx])

                # Sort antennas and their calibration data together
                combined = list(zip(existing_routings, existing_cal_data))
                combined.sort(key=lambda x: x[0])
                existing_routings[:], existing_cal_data[:] = zip(*combined)

                updated_rx = True
                break

        if not updated_rx:
            rx_carriers.append(data_rx)

    def build_iq_dc_imbalance(self, bw_list, iq_dc_imb_freq, i_dc_ua, q_dc_ua):
        """Builds the i_q_dc_imbalance structure for a band."""
        per_bw_entries = []
        iq_dc_imb_freq_khz = int(iq_dc_imb_freq / 1e3)
        for idx, bw_mhz in enumerate(bw_list):
            per_freq_entries = []
            per_freq_entries.append(
                {
                    "freq_khz": iq_dc_imb_freq_khz,
                    "i_dc_uA": i_dc_ua[idx],
                    "q_dc_uA": q_dc_ua[idx],
                }
            )
            per_bw_entries.append({"bw_mhz": bw_mhz, "per_freq": per_freq_entries})
        return per_bw_entries

    def build_iq_phase_gain_mm(
        self, bw_list, iq_gain_phase_mm_freq, gain_db, phase_degree
    ):
        """Builds the i_q_dc_imbalance structure for a band."""
        per_bw_entries = []
        iq_gain_phase_mm_freq_khz = int(iq_gain_phase_mm_freq / 1e3)
        for idx, bw_mhz in enumerate(bw_list):
            per_freq_entries = []
            per_freq_entries.append(
                {
                    "freq_khz": iq_gain_phase_mm_freq_khz,
                    "gain_db": gain_db[idx],
                    "phase_degree": phase_degree[idx],
                }
            )
            per_bw_entries.append({"bw_mhz": bw_mhz, "per_freq": per_freq_entries})
        return per_bw_entries

    def set_tx_rf_cal_data(  # noqa: PLR0912
        self,
        band: int,
        bws_hz: list[int] = None,
        freqs: list[int] = None,
        freq_pout_offsets: list[int] = None,
        rfic_lut: list[int] = None,
        pa_gains: list[int] = None,
        bw_pout_offsets: list[int] = None,
        ant2_offset: int = None,
        iq_dc_imb_freq: int = None,
        i_dc_ua: list[int] = None,
        i_dc_A: list[float] = None,
        q_dc_ua: list[int] = None,
        q_dc_A: list[float] = None,
        iq_gain_phase_mm_freq: int = None,
        gain_dB100: list[int] = None,
        gain_dB: list[int] = None,
        phase_deg10: list[int] = None,
        phase_deg: list[float] = None,
        freq_error: int = None,
    ):
        # Parameters:
        # - freq_errror: frequency error of the LO in ppb (part ber billion)

        if bws_hz is not None:
            in_bw_mhz = [int(bw_hz / 1e6) for bw_hz in bws_hz]
        tx_cal_data = {}

        # --- Optional OFFSETS ---
        offsets = {}
        if freq_pout_offsets is not None and freqs is not None:
            offsets["per_freq"] = [
                {"freq_khz": int(f / 1e3), "pout_offset": o}
                for f, o in zip(freqs, freq_pout_offsets, strict=False)
            ]

        if bw_pout_offsets is not None:
            offsets["per_bw"] = [
                {"bw_mhz": bw, "pout": p}
                for bw, p in zip(in_bw_mhz, bw_pout_offsets, strict=False)
            ]

        if rfic_lut is not None:
            offsets["rfic_lut"] = rfic_lut

        if pa_gains is not None:
            offsets["apt_pa_bias_gains"] = pa_gains

        if ant2_offset is not None:
            offsets["ant2"] = ant2_offset

        if freq_error is not None:
            offsets["freq_error"] = freq_error

        if offsets:
            tx_cal_data["offsets"] = offsets

        iq_dc_imbalance = None
        if iq_dc_imb_freq is not None and i_dc_ua is not None and q_dc_ua is not None:
            iq_dc_imbalance = {
                "per_bw": self.build_iq_dc_imbalance(
                    in_bw_mhz, iq_dc_imb_freq, i_dc_ua, q_dc_ua
                )
            }
            tx_cal_data["i_q_dc_imbalance"] = iq_dc_imbalance
        elif (
            iq_dc_imb_freq is not None and i_dc_A is not None and q_dc_A is not None
        ):
            iq_dc_imbalance = {
                "per_bw": self.build_iq_dc_imbalance(
                    in_bw_mhz,
                    iq_dc_imb_freq,
                    [round(i * 1e7) for i in i_dc_A],
                    [round(q * 1e7) for q in q_dc_A],
                )
            }
            tx_cal_data["i_q_dc_imbalance"] = iq_dc_imbalance

        iqmm_gain_phase = None
        if (
            iq_gain_phase_mm_freq is not None
            and gain_dB100 is not None
            and phase_deg10 is not None
        ):
            iqmm_gain_phase = {
                "per_bw": self.build_iq_phase_gain_mm(
                    in_bw_mhz,
                    iq_gain_phase_mm_freq,
                    [round(g * 100) for g in gain_dB100],
                    [round(p * 10) for p in phase_deg10],
                )
            }
            tx_cal_data["iqmm_gain_phase"] = iqmm_gain_phase
        elif (
            iq_gain_phase_mm_freq is not None
            and gain_dB is not None
            and phase_deg is not None
        ):
            iqmm_gain_phase = {
                "per_bw": self.build_iq_phase_gain_mm(
                    in_bw_mhz,
                    iq_gain_phase_mm_freq,
                    [round(g * 100) for g in gain_dB],
                    [round(p * 1000) for p in phase_deg],
                )
            }
            tx_cal_data["iqmm_gain_phase"] = iqmm_gain_phase

        data_tx = {"band": band, "tx_cal_data": tx_cal_data}

        if "tx_carriers" not in self.config or not isinstance(
            self.config["tx_carriers"], list
        ):
            self.config["tx_carriers"] = []

        tx_carriers = self.config["tx_carriers"]
        updated_tx = False
        new_offsets = data_tx["tx_cal_data"].get("offsets", {})

        for i, entry in enumerate(tx_carriers):  # noqa: B007
            if entry.get("band") == band:
                existing = entry["tx_cal_data"]

                if "freq_error" in new_offsets:
                    existing.setdefault("offsets", {})["freq_error"] = new_offsets[
                        "freq_error"
                    ]

                if "rfic_lut" in new_offsets:
                    existing.setdefault("offsets", {})["rfic_lut"] = new_offsets[
                        "rfic_lut"
                    ]

                if "apt_pa_bias_gains" in new_offsets:
                    existing.setdefault("offsets", {})["apt_pa_bias_gains"] = (
                        new_offsets["apt_pa_bias_gains"]
                    )

                if "ant2" in new_offsets:
                    existing.setdefault("offsets", {})["ant2"] = new_offsets["ant2"]

                if "per_freq" in new_offsets:
                    existing_offsets = existing.setdefault("offsets", {})
                    existing_freqs = existing_offsets.setdefault("per_freq", [])
                    existing_freq_map = {f["freq_khz"]: f for f in existing_freqs}

                    for new_freq in new_offsets["per_freq"]:
                        freq_khz = new_freq["freq_khz"]
                        if freq_khz in existing_freq_map:
                            existing_freq_map[freq_khz].update(new_freq)
                        else:
                            existing_freqs.append(new_freq)

                if "per_bw" in new_offsets:
                    existing_offsets = existing.setdefault("offsets", {})
                    existing_bws = existing_offsets.setdefault("per_bw", [])
                    existing_bw_map = {b["bw_mhz"]: b for b in existing_bws}

                    for new_bw in new_offsets["per_bw"]:
                        bw_mhz = new_bw["bw_mhz"]
                        if bw_mhz in existing_bw_map:
                            existing_bw_map[bw_mhz].update(new_bw)
                        else:
                            existing_bws.append(new_bw)

                if "i_q_dc_imbalance" in tx_cal_data:
                    if "i_q_dc_imbalance" not in existing:
                        existing["i_q_dc_imbalance"] = {"per_bw": []}

                    existing_dc_imb = existing["i_q_dc_imbalance"]["per_bw"]
                    new_dc_imb = data_tx["tx_cal_data"]["i_q_dc_imbalance"]["per_bw"]

                    for new_bw in new_dc_imb:
                        bw_mhz = new_bw["bw_mhz"]
                        new_freq_entry = new_bw["per_freq"][0]
                        new_freq_khz = new_freq_entry["freq_khz"]

                        for existing_bw in existing_dc_imb:
                            if existing_bw["bw_mhz"] == bw_mhz:
                                existing_freqs = existing_bw.setdefault(
                                    "per_freq", []
                                )
                                existing_freq_khz_set = {
                                    f["freq_khz"] for f in existing_freqs
                                }
                                if new_freq_khz not in existing_freq_khz_set:
                                    existing_freqs.append(new_freq_entry)
                                else:
                                    for f in existing_freqs:
                                        if f["freq_khz"] == new_freq_khz:
                                            f.update(new_freq_entry)
                                break
                        else:
                            existing_dc_imb.append(new_bw)

                if "iqmm_gain_phase" in tx_cal_data:
                    if "iqmm_gain_phase" not in existing:
                        existing["iqmm_gain_phase"] = {"per_bw": []}
                    existing_gain_phase = existing["iqmm_gain_phase"]["per_bw"]
                    new_gain_phase = data_tx["tx_cal_data"]["iqmm_gain_phase"][
                        "per_bw"
                    ]

                    for new_bw in new_gain_phase:
                        bw_mhz = new_bw["bw_mhz"]
                        new_freq_entry = new_bw["per_freq"][0]
                        new_freq_khz = new_freq_entry["freq_khz"]

                        for existing_bw in existing_gain_phase:
                            if existing_bw["bw_mhz"] == bw_mhz:
                                existing_freqs = existing_bw.setdefault(
                                    "per_freq", []
                                )
                                existing_freq_khz_set = {
                                    f["freq_khz"] for f in existing_freqs
                                }
                                if new_freq_khz not in existing_freq_khz_set:
                                    existing_freqs.append(new_freq_entry)
                                else:
                                    for f in existing_freqs:
                                        if f["freq_khz"] == new_freq_khz:
                                            f.update(new_freq_entry)
                                break
                        else:
                            existing_gain_phase.append(new_bw)
                updated_tx = True
                break

        if not updated_tx:
            tx_carriers.append(data_tx)

    def get_tx_rf_cal_data(
        self, band: int, impairment_type: list[str], bw_hz: int
    ) -> Any:
        if "tx_carriers" not in self.config:
            # Inject dummy tx_carriers to allow proceeding with fallback return
            self.config["tx_carriers"] = [{"band": band, "tx_cal_data": {}}]

        for carrier in self.config["tx_carriers"]:
            if carrier.get("band") == band:
                data = carrier.get("tx_cal_data", {})
                for key in impairment_type:
                    if key == "per_bw":
                        data_per_bw = data.get(impairment_type[0], {}).get(key)
                        if data_per_bw is None:
                            return self.get_zero_calibration(impairment_type[0])
                        if bw_hz is not None:
                            bw_mhz = int(bw_hz / 1e6)
                            per_freq_data = self.get_bw_per_bw(data_per_bw, bw_mhz)
                            return per_freq_data[0]
                        else:
                            raise KeyError(
                                f"Key '{key}' not found in path: "
                                f"{'tx_cal_data.' + '.'.join(impairment_type)}"
                            )
                return data

        if impairment_type[0] == "iqmm_gain_phase":
            na_data = {"gain_db": 0, "phase_degree": 0}
            return na_data
        elif impairment_type[0] == "i_q_dc_imbalance":
            na_data = {"i_dc_uA": 0, "q_dc_uA": 0}
            return na_data

    def get_bw_per_bw(self, data: list, bw_mhz: int):
        for entry in data:
            if entry.get("bw_mhz") == bw_mhz:
                return entry.get("per_freq")
        return [
            {
                "gain_db": 0,
                "phase_degree": 0,
                "i_dc_uA": 0,
                "q_dc_uA": 0,
            }
        ]

    def get_zero_calibration(self, cal_type: str) -> dict:
        if cal_type == "iqmm_gain_phase":
            return {"gain_db": 0, "phase_degree": 0}
        elif cal_type == "i_q_dc_imbalance":
            return {"i_dc_uA": 0, "q_dc_uA": 0}
        return {}

    def get_iq_dc_offset(self, in_band_num=41, in_rfbw_Hz=10e6):
        iq_dc_imb = self.get_tx_rf_cal_data(
            in_band_num, ["i_q_dc_imbalance", "per_bw"], in_rfbw_Hz
        )
        i_offset_A = iq_dc_imb["i_dc_uA"] * (1e-7)
        q_offset_A = iq_dc_imb["q_dc_uA"] * (1e-7)
        return i_offset_A, q_offset_A

    def get_iq_gain_phase_imbalance(self, in_band_num=41, in_rfbw_Hz=10e6):
        iq_phase_gain_imb = self.get_tx_rf_cal_data(
            in_band_num, ["iqmm_gain_phase", "per_bw"], in_rfbw_Hz
        )
        iq_gain_imbalance_dB = iq_phase_gain_imb["gain_db"] / 100
        iq_phase_imbalance_deg = iq_phase_gain_imb["phase_degree"] / 10
        return iq_gain_imbalance_dB, iq_phase_imbalance_deg
