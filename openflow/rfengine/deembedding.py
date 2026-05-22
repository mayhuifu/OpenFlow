"""Library for using deembedding data.

Ported from ``U300_RFEngine/Deembedding.py`` minus the OpenTAP scaffolding.
The original module has no OpenTAP imports or decorators at the module level
(it's a plain data loader), so the port is essentially identical save for:

* ``skrf`` is imported lazily inside the s2p branch so that the const/csv
  paths work in environments where ``scikit-rf`` is not installed. The
  original imported it at module load.

The class loads a YAML config and returns a ``[main_att, ant_att, bb_att,
coupler_att]`` quad for the requested combination via :meth:`get`.
"""
from __future__ import annotations

import csv
import logging
import os.path

import numpy as np
import yaml


class Deembedding:
    def __init__(self, filename):
        self.log = logging.getLogger(__name__)
        self.filename = filename
        with open(filename, "r") as f:
            try:
                self.config = yaml.load(f, Loader=yaml.FullLoader)
            except Exception:
                self.config = ""

    def get(self, top, uldl_config, band, frequency):
        if self.config == "":
            self.log.warning("Config file for deembedding not loaded")
            return [None, None, None, None]

        if top == "RX":
            if self.config[top][uldl_config].get(band) is not None:
                rx = self.config[top][uldl_config][band]
            else:
                rx = self.config[top][uldl_config]["default"]
            ant = self.config["Bench"][uldl_config[4:8]]
            bb = self.config["Baseband"][uldl_config[0:3]]
            coupler = self.config["Coupler"][uldl_config[4:8]]

            if rx.get("s2p") is not None:
                if not os.path.isfile(rx["s2p"]):
                    return [None, None, None, None]
                import skrf  # lazy: only needed for s2p interpolation

                nw = skrf.network.Network(rx["s2p"])
                f = skrf.Frequency.from_f(frequency, unit="Hz")
                rx_att = nw.interpolate(f, kind="cubic").s_db[0][1][0]
            elif rx.get("csv") is not None:
                if not os.path.isfile(rx["csv"]):
                    return [None, None, None, None]
                with open(rx["csv"], newline="") as csv_file:
                    reader = csv.reader(csv_file)
                    next(reader)  # discard header
                    data = list(reader)
                x = [float(row[0]) for row in data]
                y = [float(row[1]) for row in data]
                rx_att = np.interp(frequency, x, y)
            elif rx.get("const") is not None:
                rx_att = rx["const"]
            else:
                rx_att = 0.0

            if ant.get("s2p") is not None:
                if not os.path.isfile(ant["s2p"]):
                    return [None, None, None, None]
                import skrf

                nw = skrf.network.Network(ant["s2p"])
                f = skrf.Frequency.from_f(frequency, unit="Hz")
                ant_att = nw.interpolate(f, kind="cubic").s_db[0][1][0]
            elif ant.get("csv") is not None:
                if not os.path.isfile(ant["csv"]):
                    return [None, None, None, None]
                with open(ant["csv"], newline="") as csv_file:
                    reader = csv.reader(csv_file)
                    next(reader)  # discard header
                    data = list(reader)
                x = [float(row[0]) for row in data]
                y = [float(row[1]) for row in data]
                ant_att = np.interp(frequency, x, y)
            elif ant.get("const") is not None:
                ant_att = ant["const"]
            else:
                ant_att = 0.0

            if coupler.get("s2p") is not None:
                if not os.path.isfile(coupler["s2p"]):
                    return [None, None, None, None]
                import skrf

                nw = skrf.network.Network(coupler["s2p"])
                f = skrf.Frequency.from_f(frequency, unit="Hz")
                coupler_att = nw.interpolate(f, kind="cubic").s_db[0][1][0]
            elif coupler.get("csv") is not None:
                if not os.path.isfile(coupler["csv"]):
                    return [None, None, None, None]
                with open(coupler["csv"], newline="") as csv_file:
                    reader = csv.reader(csv_file)
                    next(reader)  # discard header
                    data = list(reader)
                x = [float(row[0]) for row in data]
                y = [float(row[1]) for row in data]
                coupler_att = np.interp(frequency, x, y)
            elif coupler.get("const") is not None:
                coupler_att = coupler["const"]
            else:
                coupler_att = 0.0

            if bb.get("const") is not None:
                bb_att = bb["const"]
            else:
                bb_att = 0.0

            return [rx_att, ant_att, bb_att, coupler_att]

        elif top == "TX":
            if self.config[top][uldl_config].get(band) is not None:
                tx = self.config[top][uldl_config][band]
            else:
                tx = self.config[top][uldl_config]["default"]
            ant = self.config["Bench"][uldl_config]
            bb = self.config["Baseband"]["TX"]
            coupler = self.config["Coupler"][uldl_config]

            if tx.get("s2p") is not None:
                if not os.path.isfile(tx["s2p"]):
                    return [None, None, None, None]
                import skrf

                nw = skrf.network.Network(tx["s2p"])
                f = skrf.Frequency.from_f(frequency, unit="Hz")
                tx_att = nw.interpolate(f, kind="cubic").s_db[0][1][0]
            elif tx.get("csv") is not None:
                if not os.path.isfile(tx["csv"]):
                    return [None, None, None, None]
                with open(tx["csv"], newline="") as csv_file:
                    reader = csv.reader(csv_file)
                    next(reader)  # discard header
                    data = list(reader)
                x = [float(row[0]) for row in data]
                y = [float(row[1]) for row in data]
                tx_att = np.interp(frequency, x, y)
            elif tx.get("const") is not None:
                tx_att = tx["const"]
            else:
                tx_att = 0.0

            if ant.get("s2p") is not None:
                if not os.path.isfile(ant["s2p"]):
                    return [None, None, None, None]
                import skrf

                nw = skrf.network.Network(ant["s2p"])
                f = skrf.Frequency.from_f(frequency, unit="Hz")
                ant_att = nw.interpolate(f, kind="cubic").s_db[0][1][0]
            elif ant.get("csv") is not None:
                if not os.path.isfile(ant["csv"]):
                    return [None, None, None, None]
                with open(ant["csv"], newline="") as csv_file:
                    reader = csv.reader(csv_file)
                    next(reader)  # discard header
                    data = list(reader)
                x = [float(row[0]) for row in data]
                y = [float(row[1]) for row in data]
                ant_att = np.interp(frequency, x, y)
            elif ant.get("const") is not None:
                ant_att = ant["const"]
            else:
                ant_att = 0.0

            if coupler.get("s2p") is not None:
                if not os.path.isfile(coupler["s2p"]):
                    return [None, None, None, None]
                import skrf

                nw = skrf.network.Network(coupler["s2p"])
                f = skrf.Frequency.from_f(frequency, unit="Hz")
                coupler_att = nw.interpolate(f, kind="cubic").s_db[0][1][0]
            elif coupler.get("csv") is not None:
                if not os.path.isfile(coupler["csv"]):
                    return [None, None, None, None]
                with open(coupler["csv"], newline="") as csv_file:
                    reader = csv.reader(csv_file)
                    next(reader)  # discard header
                    data = list(reader)
                x = [float(row[0]) for row in data]
                y = [float(row[1]) for row in data]
                coupler_att = np.interp(frequency, x, y)
            elif coupler.get("const") is not None:
                coupler_att = coupler["const"]
            else:
                coupler_att = 0.0

            if bb.get("const") is not None:
                bb_att = bb["const"]
            else:
                bb_att = 0.0

            return [tx_att, ant_att, bb_att, coupler_att]

        elif top == "Bench":
            _ = self.config["ANT"][uldl_config]
            return [None, None, None, None]
        elif top == "Baseband":
            _ = self.config["BB"][uldl_config[0:2]]
            return [None, None, None, None]
        elif top == "Coupler":
            _ = self.config["ANT"][uldl_config]
            return [None, None, None, None]
        return [None, None, None, None]
