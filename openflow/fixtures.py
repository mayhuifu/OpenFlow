"""User-facing pytest fixtures: config, cmw100, dut, wfg, dmm_c, dmm_v, results.

Loaded via the openflow pytest plugin entry-point. Tests that import the plugin
(automatic in this project) get all fixtures available by parameter name.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from openflow.config import OpenFlowConfig, load_config
from openflow.dut.base import Dut
from openflow.errors import InstrumentConnectError
from openflow.instruments.cmw100 import CMW100
from openflow.instruments.dmm_keysight import DMMKeysight34461A
from openflow.instruments.sa_base import SpectrumAnalyzerBase
from openflow.instruments.sa_keysight_n9020b import KeysightN9020B
from openflow.instruments.sa_rs_fsw import RsFsw
from openflow.instruments.sg_rs_smw200a import RsSmw200a
from openflow.instruments.wfg_keysight_33500b import Keysight33500B
from openflow.results import ResultsPublisher

# V3 model-name → driver-class dispatch tables. Engineers extend these
# when they add a new instrument model. Keys are stable strings used in
# `instruments.<inst>.model` YAML entries.
_SA_MODELS: dict[str, type[SpectrumAnalyzerBase]] = {
    "keysight_n9020b": KeysightN9020B,
    "rs_fsw": RsFsw,
}
_SG_MODELS: dict[str, type[RsSmw200a]] = {
    "rs_smw200a": RsSmw200a,
}
_WFG_MODELS: dict[str, type[Keysight33500B]] = {
    "keysight_33500b": Keysight33500B,
}
_DMM_MODELS: dict[str, type[DMMKeysight34461A]] = {
    "keysight_34461a": DMMKeysight34461A,
}

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(scope="session")
def config(request: pytest.FixtureRequest) -> OpenFlowConfig:
    """Load the OpenFlow YAML config specified by --openflow-config."""
    path = request.config.getoption("--openflow-config")
    if not path:
        pytest.fail("Missing --openflow-config <path-to-yaml>", pytrace=False)
    return load_config(Path(path))


@pytest.fixture(scope="session")
def cmw100(config: OpenFlowConfig) -> Generator[CMW100, None, None]:
    """Open a CMW100 session. Resources starting with 'MOCK' trigger emulation mode."""
    inst_cfg = config.instruments.get("cmw100")
    if inst_cfg is None:
        pytest.fail("config.instruments['cmw100'] is not set", pytrace=False)
    is_emul = inst_cfg.resource.startswith("MOCK")
    inst = CMW100(inst_cfg.resource, is_emulation=is_emul)
    try:
        inst.open()
    except InstrumentConnectError as e:
        pytest.fail(str(e), pytrace=False)
    yield inst
    inst.close()


@pytest.fixture(scope="session")
def dut(config: OpenFlowConfig) -> Dut:
    """Instantiate the concrete DUT class selected by config.dut.type.

    Defaults to the base Dut (V1a behavior). Concrete subclasses currently
    supported: 'u300' (DUT_U300) and 'ft2232h' (DUT_FT2232h_V03). Lazy imports
    avoid pulling pyftdi / numpy into the import path of unrelated tests.
    """
    dut_type = config.dut.type
    d: Dut
    if dut_type == "u300":
        from openflow.dut.u300 import DUT_U300
        d = DUT_U300()
        d.emulation = config.dut.emulation
    elif dut_type == "ft2232h":
        from openflow.dut.ft2232h import DUT_FT2232h_V03
        d = DUT_FT2232h_V03()  # type: ignore[no-untyped-call]
        d.emulation = config.dut.emulation
        if config.dut.ftdi_address:
            d.adress = config.dut.ftdi_address  # (sic — typo preserved from source)
        if config.dut.reg_map_file:
            d.reg_map_file = config.dut.reg_map_file
    else:
        d = Dut()
    d.open()
    return d


@pytest.fixture(scope="session")
def wfg(config: OpenFlowConfig) -> Generator[Keysight33500B, None, None]:
    """Keysight 33500B WFG (V3). MOCK:: prefix → emulation; otherwise pyvisa."""
    inst_cfg = config.instruments.get("wfg")
    resource = inst_cfg.resource if inst_cfg is not None else ""
    model = (inst_cfg.model if inst_cfg else None) or "keysight_33500b"
    cls = _WFG_MODELS[model]
    is_emul = resource.startswith("MOCK") or not resource
    inst = cls(resource, is_emulation=is_emul)
    inst.open()
    yield inst
    inst.close()


@pytest.fixture(scope="session")
def sg(config: OpenFlowConfig) -> Generator[RsSmw200a, None, None]:
    """R&S SMW200A signal generator (V3). MOCK:: → emulation."""
    inst_cfg = config.instruments.get("sg")
    resource = inst_cfg.resource if inst_cfg is not None else ""
    model = (inst_cfg.model if inst_cfg else None) or "rs_smw200a"
    cls = _SG_MODELS[model]
    is_emul = resource.startswith("MOCK") or not resource
    inst = cls(resource, is_emulation=is_emul)
    inst.open()
    yield inst
    inst.close()


@pytest.fixture(scope="session")
def sa(config: OpenFlowConfig) -> Generator[SpectrumAnalyzerBase, None, None]:
    """Spectrum analyzer (V3). Model selectable via instruments.sa.model:
    'keysight_n9020b' (default) or 'rs_fsw'."""
    inst_cfg = config.instruments.get("sa")
    resource = inst_cfg.resource if inst_cfg is not None else ""
    model = (inst_cfg.model if inst_cfg else None) or "keysight_n9020b"
    cls = _SA_MODELS[model]
    is_emul = resource.startswith("MOCK") or not resource
    inst = cls(resource, is_emulation=is_emul)
    inst.open()
    yield inst
    inst.close()


@pytest.fixture(scope="session")
def dmm_c(config: OpenFlowConfig) -> Generator[DMMKeysight34461A, None, None]:
    """Keysight 34461A DMM session for current measurements.

    Resource strings starting with 'MOCK' route to emulation mode (no pyvisa,
    canned readings) — used by CI and by tests that don't actually exercise
    the DMM. Real resources (e.g. 'TCPIP0::192.168.1.50::INSTR') open a
    pyvisa session and talk to the bench DMM.
    """
    inst_cfg = config.instruments.get("dmm_c")
    resource = inst_cfg.resource if inst_cfg is not None else ""
    is_emul = resource.startswith("MOCK") or not resource
    dmm = DMMKeysight34461A(resource, is_emulation=is_emul)
    dmm.open()
    yield dmm
    dmm.close()


@pytest.fixture(scope="session")
def dmm_v(config: OpenFlowConfig) -> Generator[DMMKeysight34461A, None, None]:
    """Keysight 34461A DMM session for voltage measurements.

    Same routing rules as ``dmm_c`` — MOCK prefix or empty resource → emulation.
    """
    inst_cfg = config.instruments.get("dmm_v")
    resource = inst_cfg.resource if inst_cfg is not None else ""
    is_emul = resource.startswith("MOCK") or not resource
    dmm = DMMKeysight34461A(resource, is_emulation=is_emul)
    dmm.open()
    yield dmm
    dmm.close()


@pytest.fixture
def results(request: pytest.FixtureRequest) -> ResultsPublisher:
    """Per-test publisher. Records flow into the session report via plugin hooks."""
    marker = request.node.get_closest_marker("testcase")
    testcase_id = marker.args[0] if (marker and marker.args) else None
    publisher = ResultsPublisher(test_node_id=request.node.nodeid, testcase_id=testcase_id)
    request.session._openflow_publishers.append(publisher)  # type: ignore[attr-defined]
    return publisher
