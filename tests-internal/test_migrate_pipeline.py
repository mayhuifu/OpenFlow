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
