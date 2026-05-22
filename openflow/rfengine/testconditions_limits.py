"""Library for using Testconditions_Limits data.

Ported from ``U300_RFEngine/Testconditions_Limits.py``. The source has no
OpenTAP scaffolding so the port is essentially the original module with a
real logger and some lint cleanup.

The class loads a YAML config keyed as ``testcase -> band -> bandwidth ->
param`` and exposes:

* :meth:`get(tc, band, bandwidth_Hz, param)` — falls back to ``default`` at
  the band and bandwidth levels.
* :meth:`get_band_modulation(tc, band, modulation, param)` — variant keyed
  on modulation instead of bandwidth.
"""
from __future__ import annotations

import logging

import yaml


class Testconditions_Limits:
    # Tell pytest not to try collecting this as a test class (the leading
    # "Test" prefix matches pytest's default collection pattern).
    __test__ = False

    def __init__(self, filename):
        self.log = logging.getLogger(__name__)
        self.filename = filename
        self.err = ""

        with open(filename) as f:
            try:
                self.config = yaml.load(f, Loader=yaml.FullLoader)
            except Exception:
                self.err = f"Testconditions_Limits: Could not load File {f}."
                self.config = ""

    def get(self, tc, band, bandwidth_Hz, param):
        bw = str(f"{bandwidth_Hz/1e6:g}")
        if self.config.get(tc):  # check if is there
            if self.config[tc].get(band) is not None:
                tcl_band = self.config[tc][band]
            else:
                tcl_band = self.config[tc]["default"]
            if tcl_band.get(bw) is not None:
                tcl = tcl_band[bw]
            else:
                tcl = tcl_band["default"]

            if tcl.get(param) is not None:
                return tcl[param]
            else:
                self.err = (
                    f"Testconditions_Limits: Parameter {param} for testcase "
                    f"{tc} in band {band}."
                )
                return None

    def get_band_modulation(self, tc, band, modulation, param):
        if self.config.get(tc):  # check if is there
            if self.config[tc].get(band) is not None:
                tcl_band = self.config[tc][band]
                tcl_band_default = self.config[tc]["default"]
            else:
                tcl_band = self.config[tc]["default"]
                tcl_band_default = None
            if tcl_band.get(modulation) is not None:
                tcl = tcl_band[modulation]
            else:
                tcl = tcl_band["default"]

            if tcl.get(param) is not None:
                return tcl[param]
            else:
                # check if param is found in <default>.<modulation>
                if (
                    tcl_band_default is not None
                    and tcl_band_default.get(modulation) is not None
                ):
                    tcl = tcl_band_default[modulation]
                else:
                    tcl = tcl_band_default["default"]

                if tcl.get(param) is not None:
                    return tcl[param]

                self.err = (
                    f"Testconditions_Limits: Parameter {param} for testcase "
                    f"{tc} in modulation {modulation}."
                )
                return None
