# OpenFlow — V2 Design (Bulk Migration + HTML Reports)

**Status:** Draft for engineering review
**Date:** 2026-05-22
**Supersedes / extends:** [`2026-05-22-openflow-v1-design.md`](./2026-05-22-openflow-v1-design.md)
**Audience:** RF engineering team + framework maintainers

---

## 1. What is V2?

V2 is the **fleet-out** phase: take the framework + migrator that v1 shipped
and run it against the **entire U300 EVT test suite**, surfacing any pattern
the v1 migrator doesn't handle and adding the transformers needed to close
those gaps. By the end of V2, every test in the existing OpenTAP suite has a
runnable pytest equivalent in `tests/`, and the bench report engineers read
is rendered as readable HTML rather than raw JSON.

V2 also lifts the two remaining intentional manual-cleanup gates from the
v1 checklist — the sweep-loop → `@pytest.mark.parametrize` rewrite (step 6)
and the `Print_Summary` cleanup — into automation, leaving only the
nested-verdict logic (step 7) as engineer judgment.

### What v1 left for V2 (current state at v0.4.0)

| Capability | v1 state | V2 target |
|---|---|---|
| Migration of TX EVM Power Sweep | ✅ Done | — |
| Migration of remaining ~12 EVT tests | ❌ Source not in repo | ✅ All migrated, in `tests/` |
| Migrator transformers | 20 (handle the 1 canonical fixture cleanly) | ~22-25 (cover patterns surfaced by bulk migration) |
| Bench report format | JSON only (`--openflow-report=report.json`) | JSON + HTML (`--openflow-html-report=report.html`) |
| Sweep loops → `parametrize` | ❌ Manual | ✅ Automated for simple cases |
| `Print_Summary` calls | ❌ Manual (left as bare-name calls in migrated output) | ✅ Automated rewrite to `logger.info` |
| Additional CMW100 measurements | TX-EVM subset only (NR) | Whatever the other 12 tests need (LTE Tx ACLR/SEM, NR FFT/SA peak, etc.) |
| Bench validation | Only TX EVM Power Sweep verified to *collect* | All ~13 tests collect; bench engineer validates 2-3 representative tests end-to-end |

### Why now

The v0.3.0 release (V1e) closed the last cheap automation wins on the canonical
fixture; v0.4.0 (V1f) closed the highest-leverage non-migrator gaps (real DMM,
DUT audit, `initialize_tx` port). The migrator is now at the point of
diminishing returns *against a single fixture*. The next leverage is **scale**:
running the migrator against the rest of the suite reveals patterns we haven't
seen, and each new pattern is one more transformer that helps every future
migration. V2 is "harden by exposure."

The HTML report is the natural V2 companion: as the test count multiplies,
the raw JSON report becomes unreadable, and engineers want a single-file
artifact they can email / archive / open in a browser.

---

## 2. V2 scope

### Success criteria

V2 is "shipped" when **all** of the following hold:

1. **All EVT tests collect cleanly.** From a clean checkout, after the
   engineer drops the remaining ~12 OpenTAP source files into a
   designated input directory:
   ```sh
   uv run openflow migrate path/to/opentap_evt_tests/*.py
   uv run pytest tests/ --collect-only
   ```
   …finds every migrated test, no `ImportError`, no collection failure.

2. **At least 2 of the 12 new tests pass end-to-end on bench.** Engineer
   picks two representative tests (e.g. one RX, one TX-but-non-EVM) and
   confirms a full sweep completes with sensible numbers. Doesn't have to
   be all 12 — that's a multi-week bench effort on real hardware. Two is
   enough to prove the framework holds.

3. **HTML report renders for the demo session.**
   ```sh
   uv run pytest tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py \
     --openflow-config=tests/configs/u300b0_evt.yaml \
     --openflow-html-report=report.html
   ```
   …produces a `report.html` that a human can open in a browser and see
   per-test verdict, per-parametrize-case measured values, and overall
   pass/fail summary. No external server, no JS framework — single file.

4. **CI still green.** 250+ internal tests passing on Ubuntu + Windows.
   Lint, type-check, no test regressions.

5. **The two automated gates close.** Re-running the migrator on the
   canonical fixture (`tests-internal/fixtures/sample_opentap_tx_evm.py`)
   emits a test that **does not need manual cleanup for** sweep-loop
   conversion or `Print_Summary`. Steps 6 and 8 of the V1b cleanup
   checklist drop to ✅.

### Explicit non-goals for V2

- Persistent results database (V4)
- Web dashboard (V5)
- Real driver ports for SG / SA / WFG (V3 — those instruments are still stubs in V2)
- Bench reservation / multi-DUT (V5)
- Test-data exchange format for cross-bench correlation (V4)
- Replacing the JSON report (HTML is a *new* artifact; JSON stays the source of truth)

---

## 3. Architecture

### New module structure (additions, not replacements)

```
openflow/
├── report/                         # NEW package — V2
│   ├── __init__.py
│   ├── html.py                     # HTMLReportRenderer (json → html)
│   ├── templates/
│   │   └── report.html.j2          # Jinja2 single-page template
│   └── static/                     # Inlined into the final HTML (no external assets)
│       ├── style.css
│       └── chart.js                # Light chart.js subset for measurement plots
├── migrate/
│   ├── transformers.py             # Adds 2-5 transformers (parametrize, print_summary, …)
│   └── ...
└── plugin.py                       # Adds --openflow-html-report CLI option
```

The HTML renderer reads the existing `results.publish(...)` JSON output. No
schema change — V2 just adds a second output format from the same data.

### New transformers for V2 migrator pass

Anticipated based on what we see in the canonical TX EVM source. The
actual set is determined by what bulk migration surfaces. Best-guess:

1. **`RewriteSweepLoops` — `for x in range(…):` → `@pytest.mark.parametrize`**
   *(closes V1b cleanup step 6)*

   Matches the simple-outer-loop pattern: a `for` whose only side effect
   on each iteration is to set the test's measurement parameter. Lifts
   the iterable into a decorator and adds the loop variable to the
   function signature. Skips loops with per-iteration setup (those stay
   as inline loops — judgment call).

2. **`RewritePrintSummary` — `Print_Summary(...)` → `logger.info(...)`**
   *(closes V1b cleanup step 8.5)*

   The OpenTAP `Print_Summary` helper was a debug-log convenience. The
   transformer drops the call or converts it to a structured `logger.info`
   that includes the same fields. Behavior preserved enough for bench
   debugging, no NameError on collection.

3. **`RewriteRxMeasurementCalls`** *(speculative — depends on what the RX tests do)*

   If the RX tests use a method shape that v1 doesn't handle (e.g. method
   chains, dict-of-results returns) we add the corresponding rewriter
   here. Driven entirely by what bulk migration shows; might be zero
   transformers if RX tests look like TX tests.

4. **`RewriteNestedVerdictSkip`** *(stretch goal — partial step 7 automation)*

   For the most common nested-verdict pattern (`if measured > limit: fail
   else if outside_range: skip else: pass`), emit a `pytest.skip(...)` for
   the skip branch automatically. Not a general solution — only the common
   pattern.

Plus whatever else surfaces. The migrator is now a regression-tested
expandable system; each new transformer ships with unit tests + a
pipeline-level assertion.

### HTML report design

Single self-contained `.html` file. No external CDN, no internet at view
time. Sections:

- **Header:** Test session metadata (date, host, openflow version, config file).
- **Summary band:** Total tests, passed, failed, skipped, duration. Color-coded.
- **Per-test rows:** One row per pytest test ID. Expandable to show all
  parametrize cases as a sub-table.
- **Per-measurement view:** Each parametrize case shows the `results.publish(...)`
  kwargs as columns. For numeric series (the common case), a small inline
  Chart.js sparkline shows the trend across parametrize values.
- **Failure detail:** Failing tests get a collapsible block showing the
  assertion message and the relevant `results.publish` row.

Rendered from the same `report.json` the framework already produces — no
plugin hook changes, just one new option:

```
--openflow-html-report=<path>     # generated alongside the JSON report
```

If both `--openflow-report` and `--openflow-html-report` are given, the
framework writes both. If only HTML is requested, the JSON is still
produced as an intermediate (engineer can delete it after if not needed).

Template: Jinja2 (already transitively available via pytest; if not, declared dep).

### Additional CMW100 surface

This is the most uncertain part of V2 scope. The TX EVM Power Sweep used
4 NR measurement methods. The other 12 EVT tests will use:

- LTE Tx measurements: ACLR, SEM, Spectrum Flatness, Carrier Leakage
- NR Tx beyond EVM: FFT, SA peak power, IBE
- RX measurements: NR Rx Power (sensitivity tests use `SA` instrument, not CMW)
- LTE Sig (in-band signaling for some RX tests)

V2 ports **on demand** — for each migrated test that needs a new method,
add it to the right CMW100 mixin (A for analyzer/measurement; G for
generator; new mixin if needed). Same `is_emulation` pattern as V1.

Estimated scope: ~10-20 new methods across the mixins, none individually
large (~50 lines each).

---

## 4. Phase split: V2a vs V2b

Pattern from V1: split into a hardware-independent phase and a
bench-validation phase.

### V2a — framework + new transformers (unblocked)

- All new migrator transformers + their unit tests + pipeline assertions
- HTML report renderer + tests against canonical JSON fixtures
- Any new CMW100 methods needed by the migrated tests (mockable / emulated)
- All ~12 EVT tests collect cleanly via `pytest --collect-only` in CI
- 250+ internal tests passing on Ubuntu + Windows

**Definition of done:** CI green; engineer can `uv run openflow migrate
*.py` on the new EVT sources and get clean test files without manual
edits beyond step 7 (the judgment gate).

### V2b — bench validation (blocked on bench availability + DUT_U300 port)

- 2 of the 12 newly-migrated tests run end-to-end on real bench
- HTML report screenshot in the bench-validation doc
- Any bench-surfaced bugs fixed (drivers, configs, fixtures)

**Definition of done:** Engineer signs off on two sample `report.html`
files matching expected verdicts.

V2 as a whole is "shipped" only when V2b is green. V2a alone is a useful
internal milestone — the migrator is provably more capable — but external
release is gated on V2b.

---

## 5. Dependencies and prerequisites

V2 depends on inputs the OpenFlow repo doesn't currently hold:

| Input | Source | Without it |
|---|---|---|
| The ~12 OpenTAP EVT source files | Engineer's UMT workspace (proprietary) | V2a still ships (migrator and HTML render are testable against synthetic fixtures), but V2 success criterion #1 is unverifiable |
| Real `configs/limits/U300B0.yaml`, `configs/deembedding/U300B0.yaml`, `configs/calibration/U300B0.yaml` | Engineer-provided | V2b cannot run; V2a can still complete |
| `rfd_simulator` port for DUT_U300 RFIC/RFFE methods | V1f flagged this as out of scope; needs `cmd_initialize` / `set_rfTxStop` / `set_rfTxPower` real bodies | V2b's full-sweep tests fail loudly per the V1f audit |
| Working CMW100 NR FR1 Meas chain (`-114` SCPI error from V1f bench session) | Bench engineer's `test_02` diagnostic run | V2b's TX measurements can't actually report values |

**V2 starts with a discovery step:** confirm that V2a's prerequisites are
in hand (source files at minimum) before committing to a full V2a
implementation.

---

## 6. Risks and unknowns

### Risk: Bulk migration surfaces too many new patterns

The single canonical fixture has 1 OpenTAP file's worth of patterns. The
other 12 may use idioms we haven't seen — e.g. multiple inheritance, dynamic
property creation, custom verdict aggregators. Each new pattern is a
transformer + tests, but a long tail of these would push V2a out by weeks.

**Mitigation:** Treat the first migrated test as the V2a scope-setter.
Migrate 1 new EVT test end-to-end manually first (or with current
migrator + manual cleanup), enumerate every cleanup the engineer had to
do, and budget the transformer work from that.

### Risk: HTML rendering inflates the test artifact size

A single HTML file with inlined Chart.js + CSS + the test data can be
hundreds of KB per session. For a CI run that produces 100+ reports, the
artifact storage adds up.

**Mitigation:** Inline only the JS / CSS we need (not full Chart.js;
hand-rolled SVG sparklines suffice for the simple case). Aim for a
sub-100 KB HTML file per test session.

### Risk: Engineers prefer to render in their own tooling

If the team has an existing report format (PDF, Excel, Grafana dashboard,
etc.) the HTML output is duplicative. Worth checking before doing the
work.

**Open question for review:** "Is the HTML report the right deliverable,
or would integration with an existing report system be more useful?"

### Risk: Bench engineer's time is the bottleneck for V2b

V2a can be parallelized with other work; V2b needs the engineer hands-on
with real hardware for each of the two validated tests. Realistically a
day per test once everything else is in place.

**Mitigation:** V2a → ship internally → V2b deferred until bench window
opens. Don't gate v0.5.0-release on V2b.

---

## 7. Open questions for engineering review

1. **EVT-test source availability.** Can the engineer make the
   remaining ~12 EVT test files available to the OpenFlow repo? If yes,
   how (private mirror, vendored under `tests/_proprietary/`, copied at
   migrator-run time only)? Affects whether V2a's pipeline-level tests
   can pin behavior across the whole suite, or only the canonical
   fixture.

2. **HTML report scope.** Stretch goal or core deliverable? If core,
   should it replace JSON (engineer-facing) or supplement it (JSON =
   machine, HTML = human)? Recommendation in this spec: supplement.

3. **CMW100 LTE methods — port faithfully or rewrite?** The existing
   CMW100ALteSig / CMW100ALteMeas mixins in the UMT codebase are sizable
   (~1000 lines each). V1a ported the NR subset by copy + strip. For
   LTE: same approach, or skinny pythonic ports?

4. **Print_Summary cleanup.** Drop the call, convert to `logger.info`, or
   convert to a structured summary publish? The original was a
   debug-aid log. Recommendation: convert to `logger.info` with the
   same fields — preserves debugging signal, no behavior change.

5. **Parametrize lift heuristic.** Where exactly is the line between
   "loop has only iteration-variable side effects" (auto-lift) and "loop
   has per-iteration setup" (leave inline)? Need 2-3 concrete examples
   from the new EVT tests to calibrate.

---

## 8. Out of band: roadmap relative position

V2 lands between v0.4.0 (V1f) and what would become v0.5.0 (V2a) + v0.6.0
(V2b). Subsequent phases:

- **V3** — Real drivers for SG / SA / WFG. *DMM was completed in V1f and is not part of V3.* See [`2026-05-22-openflow-v3-design.md`](./2026-05-22-openflow-v3-design.md).
- **V4** — Persistent results (SQLite default, optional PostgreSQL). See [`2026-05-22-openflow-v4-design.md`](./2026-05-22-openflow-v4-design.md).
- **V5** — Lab orchestration (bench reservation, multi-DUT parallel runs, read-only web dashboard). See [`2026-05-22-openflow-v5-design.md`](./2026-05-22-openflow-v5-design.md).

V3 onward is independent of V2's bulk migration — V3's instrument ports
don't depend on a particular test surface and can be sequenced based on
which instruments the engineer needs to validate first.
