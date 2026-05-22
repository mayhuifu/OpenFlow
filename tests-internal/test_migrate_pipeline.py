"""End-to-end migrator pipeline test against the real TX EVM source fixture."""
from pathlib import Path

from openflow.migrate.pipeline import migrate_source


def test_pipeline_strips_opentap_scaffolding():
    source = Path("tests-internal/fixtures/sample_opentap_tx_evm.py").read_text()
    result = migrate_source(source)
    assert "import OpenTap" not in result.code
    assert "from opentap import *" not in result.code
    assert "@attribute(OpenTap.Display" not in result.code
    assert "self.UpgradeVerdict" not in result.code
    assert "self.PublishResult" not in result.code
    assert "self.log." not in result.code
    assert "class U300B0_RFEB_EVT_TX_EVM_Power_Sweep" not in result.code
    assert "def test_u300b0_rfeb_evt_tx_evm_power_sweep" in result.code
    # Recorded structures bubble up for the engineer to see.
    assert "cmw100" in result.instrument_fixtures
    # Note: this TX EVM fixture inherits its in_* fields from U300_RFEngine_EVT_Base,
    # so ConvertInputProperties finds zero declarations in this file. The pipeline
    # exposes an `inputs` list field regardless (might be empty for inherited cases).
    assert isinstance(result.inputs, list)


def test_pipeline_rewrites_umt_import_paths():
    source = Path("tests-internal/fixtures/sample_opentap_tx_evm.py").read_text()
    result = migrate_source(source)
    assert "from UMT_Instruments.CMW100" not in result.code
    # The rewritten path should appear.
    assert "openflow.instruments.cmw100" in result.code or "CMW100" not in result.code


def test_pipeline_extracts_testcase_id():
    source = Path("tests-internal/fixtures/sample_opentap_tx_evm.py").read_text()
    result = migrate_source(source)
    assert "TESTCASE_ID = " in result.code
    assert "U300B0-RFE-EVT-005" in result.code


def test_pipeline_renames_legacy_config_field_names():
    """V1d: the three OpenTAP `*_config` file-path inputs should arrive as
    OpenFlowConfig `*_path` field names — no manual cleanup needed."""
    source = Path("tests-internal/fixtures/sample_opentap_tx_evm.py").read_text()
    result = migrate_source(source)
    # New names appear.
    assert "config.limits_path" in result.code
    assert "config.deembedding_path" in result.code
    assert "config.calibration_path" in result.code
    # Old names are gone.
    assert "conditions_limits_config" not in result.code
    assert "deembedding_config" not in result.code
    assert "calibration_file_config" not in result.code


def test_pipeline_emits_class_name_constant():
    """V1e: `self.__class__.__name__` must arrive as a runtime-safe
    `CLASS_NAME` constant — no module-scope NameError waiting to bite."""
    source = Path("tests-internal/fixtures/sample_opentap_tx_evm.py").read_text()
    result = migrate_source(source)
    # The dunder must be gone (illegal at module-function scope).
    assert "__class__.__name__" not in result.code
    # The constant must be present with the original class name.
    assert 'CLASS_NAME = "U300B0_RFEB_EVT_TX_EVM_Power_Sweep"' in result.code


def test_pipeline_rewrites_evt_helper_calls():
    """V1e: bare-name EVT helper calls must arrive as their lowercase
    module-level Python equivalents, with auto-injected import."""
    source = Path("tests-internal/fixtures/sample_opentap_tx_evm.py").read_text()
    result = migrate_source(source)
    # Lowercase calls present.
    assert "setup_dmm(dmms={})" in result.code
    assert "get_dmm(dmms={})" in result.code
    assert "get_aux(dut)" in result.code
    # CamelCase originals gone.
    assert "Setup_DMM(" not in result.code
    assert "Get_DMM(" not in result.code
    assert "Get_Aux(" not in result.code
    # Auto-import injected with all three names.
    assert "from openflow.rfengine.evt_base import" in result.code
    assert "setup_dmm" in result.code
    assert "get_dmm" in result.code
    assert "get_aux" in result.code
