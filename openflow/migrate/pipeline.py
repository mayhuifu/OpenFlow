"""Compose all libcst transformers into a single migration pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field

from openflow.migrate.transformers import (
    AddLoggingHeader,
    ConvertClassToTestFunction,
    ConvertInputProperties,
    ConvertInstrumentProperties,
    ConvertLogCalls,
    ConvertPublishResult,
    ConvertVerdictCalls,
    ExtractTestcaseId,
    RewriteBoardSerials,
    RewriteImportPaths,
    RewriteInputAttrs,
    RewriteOutputPublish,
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
    """Run all 16 transformers in order, return the rewritten code + metadata.

    Pipeline order matters:
      - Phase 1 strips OpenTAP scaffolding + collects metadata (instruments, inputs).
      - Phase 2 rewrites body content using that metadata; later transformers depend
        on earlier ones (e.g. RewriteOutputPublish needs ConvertPublishResult to
        have first emitted bare ``results.publish()`` calls).
    """
    # Phase 1 — collect metadata + strip class-level scaffolding.
    inst = ConvertInstrumentProperties()
    inputs = ConvertInputProperties()
    code = transform(
        source,
        StripOpenTapImports(),         # 1. drop opentap / clr / System imports
        RewriteImportPaths(),          # 2. UMT_* / U300_RFEngine.* → openflow.*
        StripAttributeDecorators(),    # 3. drop @attribute(OpenTap.Display(...))
        ExtractTestcaseId(),           # 4. Testcase_ID → module-level TESTCASE_ID
        inst,                          # 5. capture instrument fixture names
        inputs,                        # 6. capture input property names + defaults
        StripLifecycleStubs(),         # 7. drop trivial __init__/PreRun/PostRun
    )
    # Phase 2 — body rewrites that depend on collected metadata.
    code = transform(
        code,
        ConvertClassToTestFunction(  # 8. class+Run → def test_*(<fixtures>):
            instrument_fixtures=inst.instrument_names,
        ),
        ConvertVerdictCalls(),         # 9. UpgradeVerdict(Pass/Fail) → pass / assert False
        ConvertLogCalls(),             # 10. self.log.Info → logger.info
        ConvertPublishResult(),        # 11. self.PublishResult() → results.publish()
        # V1c additions — must run AFTER the class collapse and base rewrites.
        AddLoggingHeader(),            # 12. inject import logging + logger = ... (if needed)
        RewriteInputAttrs(),           # 13. bare in_X reads → config.X
        RewriteBoardSerials(),         # 14. RFEB_SN/RFHB_SN → config.rfeb_sn/rfhb_sn
        RewriteOutputPublish(),        # 15. results.publish() → results.publish(out_X=out_X, ...)
        StripBareExcept(),             # 16. bare `except:` → `except Exception:`
    )
    return MigrationResult(code=code,
                           instrument_fixtures=inst.instrument_names,
                           inputs=inputs.inputs)
