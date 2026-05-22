# OpenFlow — V3 Design (Real SG / SA / WFG Drivers)

**Status:** Draft for engineering review
**Date:** 2026-05-22
**Supersedes / extends:** [`2026-05-22-openflow-v1-design.md`](./2026-05-22-openflow-v1-design.md), [`2026-05-22-openflow-v2-design.md`](./2026-05-22-openflow-v2-design.md)
**Audience:** RF engineering team + framework maintainers

---

## 1. What is V3?

V3 replaces the V1a placeholder stubs for **Signal Generator (SG)**,
**Spectrum Analyzer (SA)**, and **Waveform Generator (WFG)** with real
SCPI-based driver implementations — the same shape as the Keysight 34461A
DMM driver shipped in V1f.

After V3, every instrument the migrated EVT tests touch has a real driver
behind it. The only remaining "stub" instruments are PSU and OSC, which
**no** migrated test currently uses; they stay as `_UnimplementedInstrument`
placeholders until a test that needs them migrates over.

### What's deferred from earlier phases

- **DMM** — landed in V1f (`openflow.instruments.dmm_keysight.DMMKeysight34461A`).
  Not part of V3 scope.
- **CMW100** — the all-in-one tester shipped in V1a (NR subset) and grew its
  surface in V2 as needed. Not part of V3 (it isn't a stub).

### Why V3 matters

The V1f architecture says "the DUT side has loud failures on bench" — but if
the rest of the bench is stubs, the test fails on the *first* instrument
call, not necessarily the most informative one. V3 turns those stubs into
real drivers so:

1. Tests can be incrementally bench-validated. Today the only path that
   produces useful bench data is the CMW100-only chain. With SG/SA/WFG
   real, RX sensitivity tests and multi-instrument flows become testable.
2. The framework demonstrates the "one driver per instrument, one config
   line per resource string" pattern at scale — V3 is the proof that the
   architecture generalizes beyond the CMW100 special case.
3. Engineers writing **new** tests (not migrated ones) need a complete
   instrument catalog to choose from, not stubs.

---

## 2. V3 scope

### Target instruments

| Stub | V3 target | Reasoning |
|---|---|---|
| `SG` | **R&S SMW200A** | The reference RF signal generator for U300 bench setups; supports 5G NR + LTE vector modulation natively. Pure SCPI surface (no proprietary SDK). |
| `SA` | **Keysight N9020B MXA** *or* **R&S FSW** | The two most common spectrum analyzers on RF benches. Both speak nearly-identical SCPI (`SENSe:FREQuency`, `CALCulate:MARKer`, `INITiate:IMMediate`); a thin model-agnostic base + 2 thin subclasses covers both. |
| `WFG` | **Keysight 33500B** | The default arbitrary waveform generator. SCPI-only, no vendor SDK. Used for baseband I/Q sourcing into the DUT. |

Each ships as a separate module file:

```
openflow/instruments/
├── sg_rs_smw200a.py         # R&S SMW200A signal generator
├── sa_keysight_n9020b.py    # Keysight N9020B MXA spectrum analyzer
├── sa_rs_fsw.py             # R&S FSW spectrum analyzer (sibling of N9020B)
├── wfg_keysight_33500b.py   # Keysight 33500B waveform generator
└── scpi.py                  # NEW shared SCPI session base — see §3
```

The `stubs.py` aliases (`SG`, `SA`, `WFG`) get updated to point at the
default real driver, mirroring what V1f did with `DMM`.

### Per-instrument method surface

Driven by what the migrated EVT tests actually call. Bulk migration in V2
will surface the exact list; below is the V1-based projection.

**SG (`SMW200A`):**
- `set_arb_signal_rf(frequency_Hz, power_dBm, modulation, ...)` — equivalent shape to CMW100's `set_arb_signal_rf`
- `set_rf_power(power_in_dBm)` — same as CMW100's
- `set_frequency(freq_Hz)`
- `set_modulation_state(on: bool)`
- `output_on()` / `output_off()`

**SA (`KeysightN9020B` + `RsFsw` siblings):**
- `set_center_frequency(freq_Hz)`
- `set_span(span_Hz)`
- `set_resolution_bw(rbw_Hz)`
- `set_video_bw(vbw_Hz)`
- `set_reference_level(level_dBm)`
- `trigger_sweep()` + `wait_for_sweep()`
- `meas_marker_peak()` → `(freq_Hz, power_dBm)`
- `meas_channel_power(channel_bw_Hz)` → `power_dBm`
- `meas_aclr(channels_Hz_list)` → `dict[str, dBc]`
- `screenshot(path)` (optional convenience — captures a PNG)

**WFG (`Keysight33500B`):**
- `load_arb_file(filepath)` — load an I/Q waveform from CSV/MAT
- `set_arb_sample_rate(Hz)`
- `set_arb_output_amplitude_Vpp(amp)`
- `output_on(channel: 1 | 2)` / `output_off(channel)`
- `set_sync_mode(ext: bool)`

All drivers expose `is_emulation=True` paths that record SCPI to
`_scpi_log` and return canned values, same pattern as the DMM driver.

### Success criteria

V3 is "shipped" when **all** of the following hold:

1. **Each new driver has emulation tests.** ≥10 unit tests per driver,
   covering the methods migrated EVT tests actually call. All green in
   CI on Ubuntu + Windows.

2. **Each new driver has real-hardware integration tests.** Engineer
   runs one bring-up test per instrument on the bench — the analog of
   `tests/bench_bringup/test_01_cmw100_connectivity.py` for SG/SA/WFG.
   At minimum: `*IDN?` + clean error queue.

3. **At least one migrated EVT test exercises each new driver in
   emulation.** Demonstrates the fixtures wire correctly and the test
   call sites match driver method signatures.

4. **`stubs.py` aliases redirect.** `SG = RsSmw200a`, `SA = KeysightN9020B`,
   `WFG = Keysight33500B`. Tests that import from `stubs` keep working;
   the underlying class is real.

5. **CI green.** ≥300 internal tests passing.

### Explicit non-goals for V3

- Real driver ports for PSU / OSC (deferred until a test needs them)
- Multi-instrument synchronization framework (test author handles via fixtures)
- Automatic instrument discovery / hot-plug detection (engineer specifies in YAML)
- Persistent results database (V4)
- Web dashboard (V5)
- Cross-vendor SCPI abstraction layer above what `scpi.py` provides

---

## 3. Architecture

### Shared `openflow/instruments/scpi.py`

The DMM driver (V1f) introduced the open/close/write/query pattern with
emulation support. V3 promotes that into a reusable base class:

```python
class SCPIInstrument(Instrument):
    """SCPI-over-VISA instrument base. Subclasses implement the
    instrument-specific high-level methods on top of self.write/self.query.

    Handles:
      - pyvisa session lifecycle (lazy import, clean error message if missing)
      - is_emulation mode with _scpi_log recording + _emulated_response dispatch
      - Standard *IDN? / *CLS / error-queue draining
    """
    _IDN_HINT: str = "Unknown,SCPI,EMU0,0.0"

    def __init__(self, resource: str = "", *, is_emulation: bool = False) -> None:
        ...

    def open(self) -> None: ...
    def close(self) -> None: ...
    def write(self, scpi: str) -> None: ...
    def query(self, scpi: str) -> str: ...
    def identify(self) -> str: ...
    def drain_errors(self) -> list[str]: ...

    # Subclass hook for emulation:
    def _emulated_response(self, scpi: str) -> str: ...
```

The DMM driver gets **refactored** into a subclass of `SCPIInstrument`
during V3 — this is a tidy-up, not a behavior change. Tests don't change.

### Per-instrument driver layout

Each driver:

```python
class RsSmw200a(SCPIInstrument):
    """R&S SMW200A vector signal generator."""

    _IDN_HINT = "Rohde&Schwarz,SMW200A,EMU0,1.00.00-EMU"

    def set_arb_signal_rf(self, frequency_Hz, power_dBm, modulation, ...):
        self.write(f"SOURce:FREQuency {frequency_Hz}")
        self.write(f"SOURce:POWer {power_dBm}")
        # ... modulation-specific config
        self.write("OUTPut:STATe ON")

    def set_rf_power(self, power_in_dBm: float):
        self.write(f"SOURce:POWer {power_in_dBm}")

    def _emulated_response(self, scpi: str) -> str:
        # Per-driver canned responses for queries
        ...
```

### Multi-vendor SA (the only non-trivial case)

The Keysight N9020B and R&S FSW share ~80% of their SCPI surface but
differ on specifics (e.g. trace data fetch syntax). Pattern:

```
sa_base.py            # SpectrumAnalyzerBase(SCPIInstrument) — common surface
sa_keysight_n9020b.py # KeysightN9020B(SpectrumAnalyzerBase) — Keysight overrides
sa_rs_fsw.py          # RsFsw(SpectrumAnalyzerBase) — R&S overrides
```

The base handles the "set_center_frequency" / "set_span" / standard marker
operations using the SCPI that both share. Subclasses override only the
methods that differ. Engineer picks the model in YAML (e.g.
`instruments.sa.model: keysight_n9020b` or `instruments.sa.model: rs_fsw`).

### Config model extension

Today `OpenFlowConfig.instruments` maps name → `InstrumentConfig` with
just `resource`. V3 adds an optional `model` field:

```yaml
instruments:
  sa:
    resource: "TCPIP0::192.168.1.20::INSTR"
    model: "keysight_n9020b"  # default if absent: "keysight_n9020b"
  sg:
    resource: "TCPIP0::192.168.1.21::INSTR"
    model: "rs_smw200a"       # default if absent: "rs_smw200a"
  wfg:
    resource: "TCPIP0::192.168.1.22::INSTR"
    model: "keysight_33500b"  # default if absent: "keysight_33500b"
  dmm_c:
    resource: "TCPIP0::192.168.1.30::INSTR"
    # model: "keysight_34461a" — default
```

The fixture dispatches on `inst_cfg.model`:

```python
@pytest.fixture(scope="session")
def sa(config: OpenFlowConfig) -> Generator[SpectrumAnalyzerBase, None, None]:
    inst_cfg = config.instruments.get("sa")
    model = (inst_cfg.model if inst_cfg else None) or "keysight_n9020b"
    cls = {
        "keysight_n9020b": KeysightN9020B,
        "rs_fsw": RsFsw,
    }[model]
    resource = inst_cfg.resource if inst_cfg else ""
    is_emul = resource.startswith("MOCK") or not resource
    inst = cls(resource, is_emulation=is_emul)
    inst.open()
    yield inst
    inst.close()
```

### Bench bring-up tests

Mirror the CMW100 bring-up pattern from v0.2.0:

```
tests/bench_bringup/
├── test_01_cmw100_connectivity.py     # existing
├── test_02_cmw100_nr_diagnostics.py   # existing
├── test_03_cmw100_tx_evm_smoke.py     # existing
├── test_04_dmm_connectivity.py        # NEW V3 — also covers V1f DMM
├── test_05_sg_connectivity.py         # NEW V3
├── test_06_sa_connectivity.py         # NEW V3
└── test_07_wfg_connectivity.py        # NEW V3
```

Each new bring-up test does `*IDN?` + error-queue drain. ~50 lines each,
no DUT or measurement logic. They're the engineer's first-day debugging
toolkit.

---

## 4. Phase split: V3a vs V3b

### V3a — drivers + framework wiring (unblocked)

- `SCPIInstrument` base extracted, DMM refactored onto it
- Three new driver modules (SG, SA base + 2 subclasses, WFG)
- Config model gains `model` field
- Fixtures dispatch on model name
- ≥30 unit tests across the new drivers (10+ each)
- ≥4 new bench bring-up tests (DMM + SG + SA + WFG)
- All migrated EVT tests still collect cleanly

**Definition of done:** CI green; emulation mode produces sensible
canned data for every new method.

### V3b — bench validation (blocked on bench availability)

- Each bring-up test passes against the real instrument on the bench
- One migrated test that exercises SG + SA + WFG together (e.g. an RX
  sensitivity test) runs end-to-end

**Definition of done:** Engineer signs off on the bench bring-up test
report (`*IDN?` from all 7 instruments).

V3 as a whole ships when V3b is green. V3a alone is a useful internal
milestone (drivers exist, emulation tests pass) but not a public release.

---

## 5. Risks and unknowns

### Risk: instrument model variation in the field

Different teams have different SAs / SGs. The two-subclass-per-instrument
pattern handles Keysight vs R&S, but if a third vendor (Anritsu? Tektronix?)
shows up later, that's another subclass.

**Mitigation:** Keep the model dispatch in fixtures.py — adding a model is a
new module + one dict entry. Document the contract in `docs/v3-adding-instrument-model.md`.

### Risk: SCPI command variation within a model family

E.g. the Keysight N9020A vs N9020B have small SCPI differences. We're
targeting "B" variants; "A" variants may need their own subclass.

**Mitigation:** Note model variants explicitly in the driver docstring. If
a test team needs an older variant, they subclass + override the differing
methods. Document the extension pattern.

### Risk: WFG arbitrary-waveform-file format

`load_arb_file` loads CSV or MAT files into the WFG. The migrated tests'
file format expectation is engineer-knowledge. If the WFG expects a binary
format, V3 needs a file-format converter.

**Open question for review:** "What arbitrary-waveform file format do the
migrated EVT tests assume? CSV, MAT, IQT, vendor-specific?"

### Risk: Sweep time matters

Sweep-heavy tests (RX sensitivity, ACLR with multiple bands) can take
many minutes per parametrize case if the SA's sweep settings aren't
tuned. The driver shouldn't bake in slow defaults.

**Mitigation:** Each measurement method takes the relevant timing
parameters as kwargs (RBW, VBW, sweep points). Don't hide RF judgment
inside the driver.

---

## 6. Open questions for engineering review

1. **Confirm target models.** Are SMW200A / N9020B / 33500B the right
   primaries? Other deployed models we should target as second class
   citizens?

2. **R&S FSW priority.** Include FSW as a V3a subclass, or defer until a
   bench needs it? Recommendation in this spec: include — the marginal
   work is small once N9020B is done.

3. **PSU / OSC.** Truly out of scope, or should we ship `_UnimplementedInstrument`-derived stubs that warn loudly about being unimplemented (vs.
   the current silent placeholders)?

4. **Driver vendor SDK vs. pure SCPI.** R&S has Python SDKs for many of
   their instruments (similar to `rscmw-base` for CMW100). Use the SDK
   for SMW200A and FSW (consistency with CMW100), or stay on pure SCPI
   via pyvisa (consistency with the DMM driver)?

   Trade-off: SDK is more discoverable + faster to develop; SCPI is more
   transparent + easier to debug + works across vendors. Recommendation
   in this spec: pure SCPI for V3 — keep the cross-vendor abstraction
   honest.

5. **Reduce `cmw100.py` to a subclass of `SCPIInstrument`?** The CMW100
   uses the R&S SDK, not raw SCPI, so it can't directly fit the new
   base. But it could share emulation infrastructure. Recommendation:
   no — leave CMW100 standalone; the SDK is already its abstraction.

---

## 7. Out of band: roadmap relative position

V3 follows V2 (bulk migration / HTML reports) and precedes V4 (persistent
results). V3 is **architecturally independent** of V2 — the migrator and
report renderer don't care which instrument driver is behind the
fixtures. Could in principle ship in parallel with V2, but the practical
sequencing is V2 first because:

- V2's bulk migration surfaces *which* SG/SA/WFG methods the tests
  actually call, sharpening V3's scope.
- V2's HTML report gives engineers a feedback loop for V3 bench bring-up
  (the `*IDN?` test results land in the same HTML).

After V3:
- **V4** — [Persistent results](./2026-05-22-openflow-v4-design.md)
- **V5** — [Lab orchestration](./2026-05-22-openflow-v5-design.md)
