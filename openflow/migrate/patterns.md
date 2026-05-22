# OpenTAP → OpenFlow migration patterns

This file documents the transformations applied by `openflow migrate` and the
manual cleanup that may still be required afterward. Use it as a reference
when reviewing migrator output or doing one-off ports by hand.

## Auto-applied transformations (11 stages)

| OpenTAP / pythonnet pattern | OpenFlow / pytest replacement |
|---|---|
| `from opentap import *`<br>`import OpenTap`<br>`import clr` / `clr.AddReference(...)`<br>`from System import Double, ...` | Removed entirely (`StripOpenTapImports`). |
| `from UMT_Instruments.CMW100 import CMW100`<br>`from UMT_DUTs.UMT_DUT import UMT_DUT`<br>`from U300_RFEngine.Deembedding import Deembedding` | Rewritten to `openflow.*` paths (`RewriteImportPaths`). `UMT_DUT` renamed to `Dut`. |
| `from UMT_Base.UMT_TestCase import UMT_TestCase`<br>`from .U300_RFEngine_EVT_Base import U300_RFEngine_EVT_Base` | Dropped — no openflow equivalent. The migrated test function inherits from nothing. |
| `@attribute(OpenTap.Display(...))`<br>`@attribute(OpenTap.AllowAnyChild())` | Decorator removed (`StripAttributeDecorators`). |
| `Testcase_ID = property(String, "X-Y-Z").add_attribute(...)` | Module-level `TESTCASE_ID = "X-Y-Z"` (`ExtractTestcaseId`). |
| `cmw100 = property(CMW100, None).add_attribute(...)` | Removed. Name added to test-function signature as a fixture (`ConvertInstrumentProperties`). |
| `in_band = property(String, "n78").add_attribute(...)` | Removed. Engineer moves the value to `tests/configs/<name>.yaml` (`band: n78`) (`ConvertInputProperties`). |
| `class X(U300_RFEngine_EVT_Base):` + `def Run(self): ...` | `def test_x(cmw100, ..., config, results): ...` (`ConvertClassToTestFunction`). |
| `self.foo` (anywhere in the former class body) | `foo`. |
| `self.UpgradeVerdict(OpenTap.Verdict.Pass)` | `pass` (`ConvertVerdictCalls`). |
| `self.UpgradeVerdict(OpenTap.Verdict.Fail)` | `assert False, "verdict Fail"`. |
| `self.log.Info("...")` (also Warning/Error/Debug) | `logger.info("...")` etc (`ConvertLogCalls`). |
| `self.PublishResult()` | `results.publish()  # TODO[openflow-migrate]: ...` (`ConvertPublishResult`). |
| `def __init__(self): super().__init__()`<br>`def PreRun(self): super().PreRun()`<br>`def PostRun(self): super().PostRun()` | Removed if trivial (`StripLifecycleStubs`). |

## Manual cleanup the migrator does NOT do (yet)

When running the migrator on a real OpenTAP test, expect to do these by hand:

1. **Add `import logging` / `logger = logging.getLogger(__name__)`** at the top
   of the generated file — required because `logger.info(...)` calls are
   produced but no logger is set up. (Roadmap V2: a transformer will add this header.)
2. **Choose which `out_*` variables to forward to `results.publish(...)`.** The
   migrator emits an empty `results.publish()`; you pick the kwargs from the
   `out_*` assignments earlier in the function body.
3. **Move `in_*` defaults to YAML.** The migrator records them (via
   `ConvertInputProperties`) but doesn't write the YAML — refer to the CLI
   output for the list of names + defaults to move.
4. **Convert sweep loops to `@pytest.mark.parametrize`.** A loop like
   `for gain in self.rx_gain_table:` should usually become a parametrize at the
   top of the function. Manual judgement required because nested loops, prefix
   setup, and per-iteration teardown affect the right shape.
5. **Resolve inherited `self.in_*` / `self.out_*` references.** If the original
   test inherited from `U300_RFEngine_EVT_Base` (or any other base), the migrator
   strips the inheritance — but `in_*` and `out_*` references in the body remain.
   Move what's `in_*` to YAML config and read via the `config` fixture; replace
   `out_*` with local variables; pass the local variables to `results.publish()`.
6. **Handle nested verdict logic** (e.g. `if measurement > threshold:
   UpgradeVerdict(Fail) else: log.Debug(...)`). The migrator only handles direct
   `UpgradeVerdict` calls. Nested logic needs human review — often the right
   pattern is `pytest.skip(...)` for "should not have been measured" cases and
   `assert` for "this is the real check."
7. **Replace `UMT_DUT`-specific calls.** Until V1b, `dut.<anything>()` will raise
   `NotImplementedError`. After V1b lands the real `DUT_U300` shim, you may need
   to rename a few methods.
8. **Tame the lint output.** Migrated files inherit the source's style issues
   (bare `except:`, mixed-case method names, unused locals). These are
   intentional preservations — fix them by hand once you understand each one.

## Running the migrator

```sh
uv run openflow migrate path/to/OpenTAPSource.py
# emits path/to/test_opentapsource.py and prints a summary of items to clean up.
```

CLI output for the V1a demo (TX EVM Power Sweep) looked like this:

```
wrote tests/test_u300b0_rfeb_evt_tx_evm_power_sweep.py
  test signature uses fixtures: ['cmw100', 'wfg', 'dut', 'dmm_c', 'dmm_v']
  PublishResult calls were left bare — pick out_* values to forward to results.publish()
```
