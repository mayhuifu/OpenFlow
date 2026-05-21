# OpenFlow

Lightweight CLI test runner for RF / baseband hardware test automation.

OpenFlow is a thin runner on top of [OpenTAP](https://www.opentap.io/),
reusing the engine and the ecosystem of vendor instrument plugins but
skipping the parts of OpenTAP that make distribution and CI integration
heavy — the `.TapPackage` package manager, the Keysight Editor GUI, and
the interactive TUI.

The long-term goal is a clean-room replacement for OpenTAP focused on
RF/BB testing. v1 is the smallest useful step toward that.

## Status

🚀 **v1 shipped on the `v1-implementation` branch.**
- Design: [docs/superpowers/specs/2026-05-21-openflow-v1-design.md](docs/superpowers/specs/2026-05-21-openflow-v1-design.md)
- Implementation plan: [docs/superpowers/plans/2026-05-21-openflow-v1.md](docs/superpowers/plans/2026-05-21-openflow-v1.md)

## v1 in one sentence

```
openflow run path/to/plan.TapPlan --plugins ./plugins --out results.json
```

…loads vendor plugin DLLs, runs an existing OpenTAP `.TapPlan`, writes a
structured JSON result file, and exits 0 / 1 / 2 / 130 based on the plan
verdict.

## Usage (v1)

```sh
dotnet src/OpenFlow.Cli/bin/Release/net8.0/openflow.dll run path/to/plan.TapPlan \
  --plugins ./plugins \
  --out results.json
```

Exit codes:

| Verdict | Exit |
| ------- | ---- |
| Pass    | 0    |
| Fail    | 1    |
| Error   | 2    |
| Aborted | 130  |

Setup-error codes (BSD sysexits.h): 64 usage, 65 bad plan file, 66 missing plugins dir, 70 plugin load failure.

## Build and test

```sh
dotnet build
dotnet test
```

Requires the .NET 8 SDK.

## Roadmap

1. **v1** — Thin runner on `OpenTap.dll`, `.TapPlan` → JSON results.
2. **v2** — Native YAML/JSON plan format alongside `.TapPlan`.
3. **v3** — `OpenFlow.Abstractions` (`IStep`, `Verdict`, `IInstrument`, …) with shim for existing OpenTAP step classes.
4. **v4** — Native `OpenFlow.Engine`; OpenTAP becomes optional per plan.
5. **v5** — Vendor plugin migration + source-level migration tool.
6. **v6** — Additional result destinations, parallel execution, structured logs, local result viewer.
7. **v7** — Final form: independent framework, OpenTAP is a legacy compat module.

Each version is independently useful — if priorities change after any milestone, OpenFlow remains a coherent product.

## License

TBD — see open question in the v1 design doc.
