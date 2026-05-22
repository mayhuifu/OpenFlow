"""Compose all libcst transformers into a single migration pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field

from openflow.migrate.transformers import (
    ConvertClassToTestFunction,
    ConvertInputProperties,
    ConvertInstrumentProperties,
    ConvertLogCalls,
    ConvertPublishResult,
    ConvertVerdictCalls,
    ExtractTestcaseId,
    RewriteImportPaths,
    StripAttributeDecorators,
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
    """Run all transformers in order, return the rewritten code + metadata."""
    # Phase 1 — collect metadata (instrument names, input defaults).
    # These transformers also strip class-level declarations they walk past.
    inst = ConvertInstrumentProperties()
    inputs = ConvertInputProperties()
    code = transform(
        source,
        StripOpenTapImports(),
        RewriteImportPaths(),
        StripAttributeDecorators(),
        ExtractTestcaseId(),
        inst,
        inputs,
        StripLifecycleStubs(),
    )
    # Phase 2 — body rewrites that depend on collected metadata.
    code = transform(
        code,
        ConvertClassToTestFunction(instrument_fixtures=inst.instrument_names),
        ConvertVerdictCalls(),
        ConvertLogCalls(),
        ConvertPublishResult(),
    )
    return MigrationResult(code=code,
                           instrument_fixtures=inst.instrument_names,
                           inputs=inputs.inputs)
