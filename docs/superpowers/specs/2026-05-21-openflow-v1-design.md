# OpenFlow — v1 Design & Product Roadmap

**Status:** Draft for engineering review
**Date:** 2026-05-21
**Author:** Initial brainstorm with Claude
**Audience:** Engineering reviewer(s)

---

## 1. What is OpenFlow?

OpenFlow is a lightweight CLI test runner for RF and baseband hardware test
automation. It is built as a thin runner on top of `OpenTap.dll`: it reuses the
existing OpenTAP engine and the ecosystem of vendor instrument plugins (Keysight,
R&S, NI, etc.), but skips the parts of OpenTAP that make distribution and CI
integration heavy — the `.TapPackage` package manager, the Keysight Editor GUI,
and the interactive TUI.

The long-term goal is a clean-room replacement for OpenTAP focused on RF/BB
testing. v1 is the smallest useful step toward that.

### Why not just use OpenTAP as-is?

The primary motivation is **dependency footprint**. We want a single CLI tool
plus a folder of plugin DLLs — embeddable in any CI pipeline, with no installer,
no package manager, no GUI tooling.

### Why not clean-room from day 1?

Heavy reliance on third-party OpenTAP-compiled vendor plugins. Reimplementing
the full `OpenTap.dll` public API surface (50+ types, version-fragile) before
shipping anything useful would take many person-months and create no incremental
value. Starting as a thin runner lets us deliver value in v1, learn the domain
in-flight, and factor OpenTAP out in later versions.

---

## 2. v1 Scope

### Success criterion

From a clean checkout, this command:

```
openflow run path/to/plan.TapPlan --plugins ./plugins --out results.json
```

…loads vendor plugin DLLs from `./plugins`, executes the plan via the OpenTAP
engine, writes a structured JSON result file, and exits:

| Verdict   | Exit code |
| --------- | --------- |
| Pass      | 0         |
| Fail      | 1         |
| Error     | 2         |
| Aborted   | 130       |

### Explicit non-goals for v1

- YAML / JSON plan format (v2)
- GUI or web view
- Package management / plugin marketplace
- Hot reload
- Result destinations other than JSON file
- Parallel plan execution
- Bench reservation / orchestration

### Target runtime

.NET 8 LTS, cross-platform (Windows and Linux CI runners). Vendor plugins are
expected to be .NET 8-compatible; if a critical plugin is .NET Framework-only,
that becomes a v1.x scope question.

---

## 3. Architecture

Two .NET 8 projects in one solution, plus a test project:

| Project          | Type           | Responsibility                                                              |
| ---------------- | -------------- | --------------------------------------------------------------------------- |
| `OpenFlow.Core`  | class library  | Plugin discovery, plan loading, plan execution, result serialization        |
| `OpenFlow.Cli`   | console app    | Argument parsing, dispatch to `PlanRunner`, verdict → exit-code mapping     |
| `OpenFlow.Core.Tests` | xUnit test project | Unit + integration tests with a tiny fixture-plugin DLL                |

### Key types (sketch)

```csharp
// OpenFlow.Core
public sealed class PlanRunner
{
    public Task<RunResult> RunAsync(RunOptions options, CancellationToken ct);
}

public sealed record RunOptions(
    string PlanPath,
    string PluginsDir,
    string OutputPath,
    LogVerbosity Verbosity);

public sealed record RunResult(
    Verdict Verdict,
    TimeSpan Duration,
    int StepCount,
    string OutputPath,
    string? ErrorMessage);

internal sealed class JsonResultListener : OpenTap.IResultListener { /* ... */ }
```

No DI container, no plugin model of our own, no config files. Deliberately
small.

---

## 4. Data flow

```
CLI args ──► PlanRunner.RunAsync
                │
                ├─► PluginLoader: assembly load from --plugins folder
                │       (delegates to OpenTap's PluginManager.SearchPlugins)
                │
                ├─► OpenTap.TestPlan.Load(planPath)   ── parses .TapPlan XML
                │
                ├─► Attach JsonResultListener (our IResultListener impl)
                │       buffers ResultTable/Verdict events into a tree
                │
                ├─► plan.Execute()                    ── OpenTAP runs the steps
                │
                └─► JsonResultListener.WriteTo(--out path)
                            └─► RunResult { Verdict, Duration, StepCount, OutPath }

CLI maps RunResult.Verdict to process exit code.
```

---

## 5. Error handling

Fail fast and loud. No retries, no recovery — lab automation users want clear,
immediate signals.

| Condition                            | Behavior                                                                   | Exit code |
| ------------------------------------ | -------------------------------------------------------------------------- | --------- |
| Invalid CLI arguments                | Print usage, exit                                                          | 64        |
| Plugin folder missing or empty       | Clear message naming the path                                              | 66        |
| `.TapPlan` file missing / malformed  | Propagate OpenTAP exception message                                        | 65        |
| Plugin load failure                  | Log the offending DLL and `ReflectionTypeLoadException.LoaderExceptions`   | 70        |
| Step throws during execution         | Captured in JSON result under `error`; verdict = Error                     | 2         |
| Ctrl+C / SIGTERM                     | Cancel via `CancellationToken`, flush partial results                      | 130       |

---

## 6. Testing strategy

Three layers, no live hardware in CI:

1. **Unit tests** — argument parsing, exit-code mapping, JSON result
   serialization. No OpenTAP needed.
2. **Integration tests** — a tiny `Fixtures.TestSteps.dll` in the test project
   containing `PassStep`, `FailStep`, and `ThrowStep`, plus fixture
   `.TapPlan` files. Verifies the full load → run → JSON → exit-code path.
3. **CI smoke test** — `openflow run` against the fixture plan on Windows and
   Linux GitHub Actions runners.

Live-instrument tests live in a separate `bench-tests/` folder, run manually
against real benches. Out of CI scope.

---

## 7. Product roadmap

The end-state goal is a clean-room replacement for OpenTAP. The roadmap is
designed so each version is independently useful — if priorities change after
any milestone, we have a coherent product.

### v1 — Thin runner *(this document)*
CLI runs `.TapPlan` XML via `OpenTap.dll`, writes JSON results.
**OpenTAP dependency: full.**

### v2 — Native plan format
Add YAML/JSON plan loader behind an `IPlanLoader` seam. `.TapPlan` still
supported. Step *types* still resolved through OpenTAP's plugin manager. Plans
authored in OpenFlow YAML become portable to a future engine.
**OpenTAP dependency: full, but plan format is no longer OpenTAP's.**

### v3 — Native abstractions (with shim)
Introduce `OpenFlow.Abstractions` with our own `IStep`, `Verdict`, `IInstrument`,
`IDut`, `IResultListener`, plus attributes (`Display`, `Output`, `Result`,
`EnabledIf`, etc.). Ship an adapter that exposes existing `OpenTap.TestStep`
classes as `OpenFlow.IStep` at runtime. New code targets our API.
**OpenTAP dependency: still loaded, but new code targets OpenFlow.**

### v4 — Native engine (alongside OpenTAP)
Build `OpenFlow.Engine` capable of running plans written purely against
`OpenFlow.Abstractions`. Engine has compat mode for shimmed OpenTAP steps when a
plan needs them. A plan composed entirely of OpenFlow-native steps runs without
touching `OpenTap.dll`.
**OpenTAP dependency: optional per plan.**

### v5 — Vendor plugin migration
For each heavily-used vendor plugin family, build OpenFlow-native equivalents,
typically as SCPI/VISA-level wrappers via `Ivi.Visa`. Ship a source-level
migration tool that rewrites OpenTAP step `.cs` files to OpenFlow step files
(namespace swaps, attribute renames, base-class change).
**OpenTAP dependency: removable from real plans.**

### v6 — Productization
Now that we own the engine: additional result destinations (CSV, InfluxDB,
ResultStore), parallel plan execution, structured logging, a small local web
view for browsing result files.
**OpenTAP dependency: optional and rare.**

### v7 — Final form
Default plans, instruments, and steps all OpenFlow-native. `OpenTap.dll` is a
legacy compat module installed on demand. Independent framework, clean small
surface, RF/BB-focused.
**Done.**

---

## 8. Open questions for the engineering reviewer

1. **Plugin runtime compatibility.** Are all our critical vendor plugin DLLs
   .NET 8-compatible, or are any pinned to .NET Framework 4.x? If the latter,
   v1 may need to ship Framework binaries alongside .NET 8 binaries, or we
   defer those plugins to a v1.x.
2. **`OpenTap.dll` distribution.** Do we vendor it as a NuGet reference,
   submodule, or copy-in? NuGet is preferred if a compatible package exists for
   the OpenTAP version our plugins target.
3. **JSON result schema.** Do we want to match OpenTAP's `ResultTable` shape
   one-to-one, or define our own simpler schema? Matters when v6 result
   destinations need to round-trip with existing OpenTAP tools.
4. **VISA on Linux.** v1 targets cross-platform .NET 8. Vendor plugins that
   depend on Windows-only native VISA libraries will not run on Linux. Is
   "Windows for real benches, Linux for fixture-based CI smoke tests" an
   acceptable v1 reality?
5. **License.** This is a public repo on GitHub. MIT, Apache-2.0, or
   something else? Note: OpenTAP itself is MPL-2.0 — interaction with our
   chosen license should be reviewed.
