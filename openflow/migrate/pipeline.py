"""Compose all libcst transformers into a single migration pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field

from openflow.migrate.transformers import (
    AddLoggingHeader,
    CaptureClassName,
    ConvertClassToTestFunction,
    ConvertInputProperties,
    ConvertInstrumentProperties,
    ConvertLogCalls,
    ConvertPublishResult,
    ConvertVerdictCalls,
    ExtractTestcaseId,
    RewriteBoardSerials,
    RewriteClassDunderName,
    RewriteConfigNames,
    RewriteEvtHelperCalls,
    RewriteImportPaths,
    RewriteInputAttrs,
    RewriteOutputPublish,
    RewritePrintSummary,
    RewriteSweepLoops,
    StripAttributeDecorators,
    StripBareExcept,
    StripLifecycleStubs,
    StripOpenTapImports,
    transform,
)


@dataclass(slots=True)
class MigrationResult:
    code: str
    instrument_fixtures: list[str] = field(default_factory=list)
    inputs: list[tuple[str, str]] = field(default_factory=list)


def migrate_source(source: str) -> MigrationResult:
    """Run all 22 transformers in order, return the rewritten code + metadata.

    Pipeline order matters:
      - Phase 1 strips OpenTAP scaffolding + collects metadata (instruments,
        inputs, class name).
      - Phase 2 rewrites body content using that metadata; later transformers
        depend on earlier ones (e.g. RewriteOutputPublish needs
        ConvertPublishResult to have first emitted bare ``results.publish()``
        calls; RewriteClassDunderName needs CaptureClassName's recorded name).
    """
    # Phase 1 — collect metadata + strip class-level scaffolding.
    inst = ConvertInstrumentProperties()
    inputs = ConvertInputProperties()
    cls_capture = CaptureClassName()
    code = transform(
        source,
        StripOpenTapImports(),         # 1. drop opentap / clr / System imports
        RewriteImportPaths(),          # 2. UMT_* / U300_RFEngine.* → openflow.*
        StripAttributeDecorators(),    # 3. drop @attribute(OpenTap.Display(...))
        ExtractTestcaseId(),           # 4. Testcase_ID → module-level TESTCASE_ID
        inst,                          # 5. capture instrument fixture names
        inputs,                        # 6. capture input property names + defaults
        cls_capture,                   # 7. capture original TestStep class name
        StripLifecycleStubs(),         # 8. drop trivial __init__/PreRun/PostRun
    )
    # Phase 2 — body rewrites that depend on collected metadata.
    code = transform(
        code,
        ConvertClassToTestFunction(    # 9. class+Run → def test_*(<fixtures>):
            instrument_fixtures=inst.instrument_names,
        ),
        ConvertVerdictCalls(),         # 10. UpgradeVerdict(Pass/Fail) → pass / assert False
        ConvertLogCalls(),             # 11. self.log.Info → logger.info
        ConvertPublishResult(),        # 12. self.PublishResult() → results.publish()
        # V1c additions — must run AFTER the class collapse and base rewrites.
        AddLoggingHeader(),            # 13. inject import logging + logger = ... (if needed)
        RewriteInputAttrs(),           # 14. bare in_X reads → config.X
        RewriteConfigNames(),          # 15. config.<old_input> → config.<new_field>
        RewriteBoardSerials(),         # 16. RFEB_SN/RFHB_SN → config.rfeb_sn/rfhb_sn
        RewriteOutputPublish(),        # 17. results.publish() → results.publish(out_X=out_X, ...)
        # V1e additions — close the last two manual-cleanup steps.
        RewriteClassDunderName(        # 18. __class__.__name__ → CLASS_NAME constant
            class_name=cls_capture.class_name,
        ),
        RewriteEvtHelperCalls(),       # 19. Setup_DMM/Get_DMM/Get_Aux → lowercase + auto-import
        RewritePrintSummary(),         # 20. Print_Summary(...) → logger.info(...)   (V2)
        RewriteSweepLoops(),           # 21. for x in [...]: ... → @pytest.mark.parametrize  (V2)
        StripBareExcept(),             # 22. bare `except:` → `except Exception:`
    )
    return MigrationResult(code=code,
                           instrument_fixtures=inst.instrument_names,
                           inputs=inputs.inputs)
