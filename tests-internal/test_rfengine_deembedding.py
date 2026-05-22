"""Tests for openflow.rfengine.deembedding (ported from U300_RFEngine/Deembedding.py).

The Deembedding class loads a YAML config and exposes ``get(top, uldl_config,
band, frequency)`` which returns the four attenuation values
``[rx_or_tx_att, ant_att, bb_att, coupler_att]`` for the requested combination.

V1a only exercises the const-path (no .s2p/.csv interpolation files) so the
tests can stay hermetic.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from openflow.rfengine.deembedding import Deembedding


# A minimal YAML covering one RX and one TX path so we can verify lookups.
SAMPLE_YAML = """
RX:
  RX0ANT0:
    default:
      const: -1.0
    n1:
      const: -2.5
TX:
  ANT0:
    default:
      const: -3.0
    n8:
      const: -4.5
Bench:
  ANT0:
    const: -0.5
Baseband:
  RX0:
    const: -0.1
  TX:
    const: -0.2
Coupler:
  ANT0:
    const: -0.7
"""


@pytest.fixture()
def yaml_config(tmp_path: Path) -> Path:
    cfg = tmp_path / "deembedding.yaml"
    cfg.write_text(SAMPLE_YAML)
    return cfg


def test_deembedding_can_be_instantiated(yaml_config: Path) -> None:
    de = Deembedding(str(yaml_config))
    assert de.filename == str(yaml_config)
    assert isinstance(de.config, dict)


def test_deembedding_get_tx_known_band(yaml_config: Path) -> None:
    de = Deembedding(str(yaml_config))
    tx_att, ant_att, bb_att, coupler_att = de.get(
        top="TX",
        uldl_config="ANT0",
        band="n8",
        frequency=1.2e9,
    )
    assert tx_att == pytest.approx(-4.5)
    assert ant_att == pytest.approx(-0.5)
    assert bb_att == pytest.approx(-0.2)
    assert coupler_att == pytest.approx(-0.7)


def test_deembedding_get_tx_falls_back_to_default(yaml_config: Path) -> None:
    de = Deembedding(str(yaml_config))
    tx_att, _, _, _ = de.get(
        top="TX",
        uldl_config="ANT0",
        band="nUNKNOWN",
        frequency=1.2e9,
    )
    assert tx_att == pytest.approx(-3.0)


def test_deembedding_unparseable_config_returns_none_quad(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    # write something that is valid YAML but produces a non-dict, so
    # downstream lookups would explode -- mirror the source's "no config" path
    # by emptying it after construction.
    bad.write_text("RX: {}\n")
    de = Deembedding(str(bad))
    de.config = ""  # simulate the parse-failed branch
    assert de.get("RX", "RX0ANT0", "n1", 1.2e9) == [None, None, None, None]
