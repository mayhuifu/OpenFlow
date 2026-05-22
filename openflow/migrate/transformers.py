"""libcst transformers that convert an OpenTAP-Python test source into a pytest test."""
from __future__ import annotations

import re

import libcst as cst
from libcst import (
    RemovalSentinel,
    matchers,  # noqa: F401
)


def transform(source: str, *transformers: cst.CSTTransformer) -> str:
    """Apply a chain of transformers to source code, return the rewritten text."""
    tree = cst.parse_module(source)
    for t in transformers:
        tree = tree.visit(t)
    return tree.code


# --- 1. Strip OpenTAP / CLR / System imports ----------------------------------

_OPENTAP_TOPLEVEL_NAMES = {"opentap", "OpenTap", "clr", "System"}


def _attr_root_name(attr: cst.Attribute | cst.Name) -> str:
    """Walk left through an Attribute chain to find the root Name."""
    node: cst.BaseExpression = attr
    while isinstance(node, cst.Attribute):
        node = node.value
    return node.value if isinstance(node, cst.Name) else ""


def _import_targets_opentap(node: cst.Import | cst.ImportFrom) -> bool:
    if isinstance(node, cst.Import):
        return any(
            (alias.name.value if isinstance(alias.name, cst.Name)
             else _attr_root_name(alias.name)) in _OPENTAP_TOPLEVEL_NAMES
            for alias in node.names
        )
    # ImportFrom
    if node.module is None:
        return False
    name = (node.module.value if isinstance(node.module, cst.Name)
            else _attr_root_name(node.module))
    return name in _OPENTAP_TOPLEVEL_NAMES


class StripOpenTapImports(cst.CSTTransformer):
    """Remove ``import opentap*``, ``import OpenTap``, ``import clr``, ``from System...``
    and ``clr.AddReference(...)`` calls at module scope."""

    def leave_SimpleStatementLine(
            self, original_node: cst.SimpleStatementLine,
            updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        new_body: list[cst.BaseSmallStatement] = []
        for stmt in updated_node.body:
            if isinstance(stmt, (cst.Import, cst.ImportFrom)):
                if _import_targets_opentap(stmt):
                    continue
            if isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.Call):
                func = stmt.value.func
                # clr.AddReference(...)
                if (isinstance(func, cst.Attribute)
                        and isinstance(func.value, cst.Name)
                        and func.value.value == "clr"
                        and isinstance(func.attr, cst.Name)
                        and func.attr.value == "AddReference"):
                    continue
            new_body.append(stmt)
        if not new_body:
            return RemovalSentinel.REMOVE
        return updated_node.with_changes(body=tuple(new_body))


# --- 2. Strip @attribute(OpenTap.*) decorators --------------------------------

class StripAttributeDecorators(cst.CSTTransformer):
    """Remove ``@attribute(OpenTap.XYZ(...))`` decorators from any class or function."""

    def _is_opentap_attribute_decorator(self, decorator: cst.Decorator) -> bool:
        d = decorator.decorator
        # decorator should be a Call of `attribute(OpenTap.something(...))`
        if not isinstance(d, cst.Call):
            return False
        if not isinstance(d.func, cst.Name) or d.func.value != "attribute":
            return False
        if not d.args:
            return False
        inner = d.args[0].value
        # inner is typically Call(func=Attribute(value=Name('OpenTap'), attr=Name('Display')), ...)
        if not isinstance(inner, cst.Call):
            return False
        f = inner.func
        if isinstance(f, cst.Attribute):
            base = f.value
            return isinstance(base, cst.Name) and base.value == "OpenTap"
        return False

    def leave_ClassDef(self, original_node: cst.ClassDef,
                       updated_node: cst.ClassDef) -> cst.ClassDef:
        kept = tuple(d for d in updated_node.decorators
                     if not self._is_opentap_attribute_decorator(d))
        return updated_node.with_changes(decorators=kept)

    def leave_FunctionDef(self, original_node: cst.FunctionDef,
                          updated_node: cst.FunctionDef) -> cst.FunctionDef:
        kept = tuple(d for d in updated_node.decorators
                     if not self._is_opentap_attribute_decorator(d))
        return updated_node.with_changes(decorators=kept)


# --- 3. Extract `Testcase_ID = property(String, "X-Y-Z")...` to module-level ---

class ExtractTestcaseId(cst.CSTTransformer):
    """Lift Testcase_ID class attribute into a module-level TESTCASE_ID constant."""

    def __init__(self) -> None:
        super().__init__()
        self._extracted_id: str | None = None

    def leave_ClassDef(self, original_node: cst.ClassDef,
                       updated_node: cst.ClassDef) -> cst.ClassDef:
        new_body: list[cst.BaseStatement] = []
        for stmt in updated_node.body.body:
            if self._is_testcase_id_assign(stmt):
                self._extracted_id = self._extract_id_string(stmt)
                continue  # drop from class body
            new_body.append(stmt)
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=tuple(new_body)))

    def leave_Module(self, original_node: cst.Module,
                     updated_node: cst.Module) -> cst.Module:
        if self._extracted_id is None:
            return updated_node
        module_stmt = cst.parse_statement(
            f'TESTCASE_ID = "{self._extracted_id}"\n')
        body = list(updated_node.body)
        insert_at = self._first_non_metadata_index(body)
        body.insert(insert_at, module_stmt)
        return updated_node.with_changes(body=tuple(body))

    @staticmethod
    def _is_testcase_id_assign(stmt: cst.BaseStatement) -> bool:
        if not isinstance(stmt, cst.SimpleStatementLine):
            return False
        for sub in stmt.body:
            if isinstance(sub, cst.Assign):
                for tgt in sub.targets:
                    t = tgt.target
                    if isinstance(t, cst.Name) and t.value == "Testcase_ID":
                        return True
        return False

    @staticmethod
    def _extract_id_string(stmt: cst.BaseStatement) -> str:
        # Find a quoted string-literal arg containing a hyphen (looks like a testcase ID).
        for node in cst.matchers.findall(stmt, cst.matchers.SimpleString()):
            text = node.value  # includes quotes
            stripped = text[1:-1] if len(text) >= 2 and text[0] in "\"'" else text
            if "-" in stripped:
                return stripped
        return "UNKNOWN-TESTCASE-ID"

    @staticmethod
    def _first_non_metadata_index(body: list[cst.BaseStatement]) -> int:
        for i, stmt in enumerate(body):
            if isinstance(stmt, cst.SimpleStatementLine):
                if all(isinstance(s, (cst.Import, cst.ImportFrom)) for s in stmt.body):
                    continue
                first = stmt.body[0] if stmt.body else None
                if isinstance(first, cst.Expr) and isinstance(first.value, cst.SimpleString):
                    continue
                if isinstance(first, cst.Assign) and len(first.targets) == 1:
                    t = first.targets[0].target
                    if isinstance(t, cst.Name) and t.value.startswith("__"):
                        continue
            return i
        return len(body)


# --- 4. Strip instrument `property(<Type>, None).add_attribute(...)` decls -----

_INSTRUMENT_TYPES = {"CMW100", "WFG", "DMM", "UMT_DUT", "SG", "SA", "VSA", "PSU", "OSC"}


def _outermost_call(node: cst.CSTNode) -> cst.Call | None:
    """Walk an Attribute chain to its innermost Call.

    E.g. property(...).add_attribute(...) has innermost Call = property(...).
    """
    while True:
        if isinstance(node, cst.Call):
            if isinstance(node.func, cst.Attribute):
                node = node.func.value  # step into the value of the attribute
                continue
            return node
        return None


class ConvertInstrumentProperties(cst.CSTTransformer):
    """Record `<name> = property(<InstrumentType>, None).add_attribute(...)` declarations
    on each class, then remove them. The recorded names show up via
    ``self.instrument_names`` for the pipeline to inject as test-function args."""

    def __init__(self) -> None:
        super().__init__()
        self.instrument_names: list[str] = []

    def leave_ClassDef(self, original_node: cst.ClassDef,
                       updated_node: cst.ClassDef) -> cst.ClassDef:
        new_body: list[cst.BaseStatement] = []
        for stmt in updated_node.body.body:
            name = self._instrument_property_name(stmt)
            if name is not None:
                self.instrument_names.append(name)
                continue
            new_body.append(stmt)
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=tuple(new_body)))

    @staticmethod
    def _instrument_property_name(stmt: cst.BaseStatement) -> str | None:
        if not isinstance(stmt, cst.SimpleStatementLine):
            return None
        for sub in stmt.body:
            if not isinstance(sub, cst.Assign):
                continue
            if len(sub.targets) != 1:
                continue
            tgt = sub.targets[0].target
            if not isinstance(tgt, cst.Name):
                continue
            rhs = sub.value
            call = _outermost_call(rhs)
            if call is None:
                continue
            if not (isinstance(call.func, cst.Name) and call.func.value == "property"):
                continue
            if not call.args:
                continue
            first_arg = call.args[0].value
            if isinstance(first_arg, cst.Name) and first_arg.value in _INSTRUMENT_TYPES:
                return tgt.value
        return None


# --- 5. Strip `in_<name> = property(<Type>, <default>)...` input declarations --

_INPUT_PROPERTY_TYPES = {"Double", "Int32", "Int64", "String", "Boolean"}


class ConvertInputProperties(cst.CSTTransformer):
    """Record `in_* = property(<scalar-type>, <default>)...` decls and strip them.
    The pipeline uses ``self.inputs`` to emit a YAML migration TODO."""

    def __init__(self) -> None:
        super().__init__()
        self.inputs: list[tuple[str, str]] = []

    def leave_ClassDef(self, original_node: cst.ClassDef,
                       updated_node: cst.ClassDef) -> cst.ClassDef:
        new_body: list[cst.BaseStatement] = []
        for stmt in updated_node.body.body:
            captured = self._input_property(stmt)
            if captured is not None:
                self.inputs.append(captured)
                continue
            new_body.append(stmt)
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=tuple(new_body)))

    def _input_property(self, stmt: cst.BaseStatement) -> tuple[str, str] | None:
        if not isinstance(stmt, cst.SimpleStatementLine):
            return None
        for sub in stmt.body:
            if not isinstance(sub, cst.Assign) or len(sub.targets) != 1:
                continue
            tgt = sub.targets[0].target
            if not (isinstance(tgt, cst.Name) and tgt.value.startswith("in_")):
                continue
            call = _outermost_call(sub.value)
            if call is None or len(call.args) < 2:
                continue
            if not (isinstance(call.func, cst.Name) and call.func.value == "property"):
                continue
            first = call.args[0].value
            if not (isinstance(first, cst.Name) and first.value in _INPUT_PROPERTY_TYPES):
                continue
            second = call.args[1].value
            try:
                default_src = cst.Module(body=[]).code_for_node(second)
            except Exception:
                default_src = "?"
            return tgt.value, default_src
        return None


# --- 6. Convert TestStep class -> module-level test_<snake>() function --------


def _to_snake_case(name: str) -> str:
    # If the input already has underscores (typical for OpenTAP test classes
    # like U300B0_RFEB_EVT_TX_EVM_Power_Sweep), just lowercase it — splitting
    # further would insert spurious underscores between digits and capitals.
    if "_" in name:
        return name.lower()
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.lower()


class ConvertClassToTestFunction(cst.CSTTransformer):
    """Replace a single TestStep class with a module-level test function.

    instrument_fixtures: names captured by ConvertInstrumentProperties — these
                        plus 'config' and 'results' form the test signature."""

    def __init__(self, instrument_fixtures: list[str]) -> None:
        super().__init__()
        self.instrument_fixtures = instrument_fixtures
        self._inside_class = False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self._inside_class = True
        return True

    def leave_ClassDef(self, original_node: cst.ClassDef,
                       updated_node: cst.ClassDef) -> cst.CSTNode | RemovalSentinel:
        self._inside_class = False
        # Find the Run method.
        run_body: cst.IndentedBlock | None = None
        for stmt in updated_node.body.body:
            if isinstance(stmt, cst.FunctionDef) and stmt.name.value == "Run":
                run_body = stmt.body
                break
        if run_body is None:
            return updated_node  # nothing to do
        # Strip `super().Run()` first statement if present.
        body_statements = list(run_body.body)
        if body_statements and self._is_super_run(body_statements[0]):
            body_statements = body_statements[1:]
        new_block = run_body.with_changes(body=tuple(body_statements))
        # Build the new test function signature.
        fixture_names = [*self.instrument_fixtures, "config", "results"]
        params = cst.Parameters(params=tuple(
            cst.Param(name=cst.Name(value=n)) for n in fixture_names
        ))
        func_name = "test_" + _to_snake_case(updated_node.name.value)
        new_func = cst.FunctionDef(
            name=cst.Name(value=func_name),
            params=params,
            body=new_block,
        )
        return new_func

    @staticmethod
    def _is_super_run(stmt: cst.BaseStatement) -> bool:
        if not isinstance(stmt, cst.SimpleStatementLine):
            return False
        for sub in stmt.body:
            if isinstance(sub, cst.Expr) and isinstance(sub.value, cst.Call):
                call = sub.value
                if (isinstance(call.func, cst.Attribute)
                        and isinstance(call.func.attr, cst.Name)
                        and call.func.attr.value == "Run"
                        and isinstance(call.func.value, cst.Call)
                        and isinstance(call.func.value.func, cst.Name)
                        and call.func.value.func.value == "super"):
                    return True
        return False

    def leave_Attribute(self, original_node: cst.Attribute,
                        updated_node: cst.Attribute) -> cst.CSTNode:
        # Strip `self.foo` → `foo` everywhere in the (former) class body.
        if (isinstance(updated_node.value, cst.Name)
                and updated_node.value.value == "self"):
            return updated_node.attr
        return updated_node


# --- 7. UpgradeVerdict(OpenTap.Verdict.Pass|Fail) → no-op / assert False ------

class ConvertVerdictCalls(cst.CSTTransformer):
    """Rewrite ``UpgradeVerdict(OpenTap.Verdict.X)`` calls."""

    def leave_SimpleStatementLine(
            self, original_node: cst.SimpleStatementLine,
            updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine:
        new_body: list[cst.BaseSmallStatement] = []
        for stmt in updated_node.body:
            replacement = self._rewrite(stmt)
            new_body.append(replacement if replacement is not None else stmt)
        return updated_node.with_changes(body=tuple(new_body))

    def _rewrite(self, stmt: cst.BaseSmallStatement) -> cst.BaseSmallStatement | None:
        if not isinstance(stmt, cst.Expr) or not isinstance(stmt.value, cst.Call):
            return None
        call = stmt.value
        is_match = False
        if isinstance(call.func, cst.Name) and call.func.value == "UpgradeVerdict":
            is_match = True
        elif (isinstance(call.func, cst.Attribute)
              and isinstance(call.func.attr, cst.Name)
              and call.func.attr.value == "UpgradeVerdict"):
            is_match = True
        if not is_match or not call.args:
            return None
        arg = call.args[0].value
        verdict = self._verdict_name(arg)
        if verdict == "Pass":
            return cst.Pass()
        if verdict in ("Fail", "Error", "Aborted", "Inconclusive"):
            return cst.Assert(
                test=cst.Name("False"),
                msg=cst.SimpleString(f'"verdict {verdict}"'))
        return None

    @staticmethod
    def _verdict_name(node: cst.CSTNode) -> str | None:
        if isinstance(node, cst.Attribute) and isinstance(node.attr, cst.Name):
            return node.attr.value
        return None


# --- 8. self.log.Level(...) → logger.level(...) -------------------------------

_LOG_LEVEL_MAP = {"Info": "info", "Warning": "warning",
                  "Error": "error", "Debug": "debug"}


class ConvertLogCalls(cst.CSTTransformer):
    """Rewrite ``self.log.Info(x)``/``log.Info(x)`` → ``logger.info(x)``."""

    def leave_Call(self, original_node: cst.Call,
                   updated_node: cst.Call) -> cst.Call:
        attr = updated_node.func
        if not isinstance(attr, cst.Attribute):
            return updated_node
        level_name = attr.attr.value if isinstance(attr.attr, cst.Name) else None
        if level_name not in _LOG_LEVEL_MAP:
            return updated_node
        # Verify the base is `<...>.log` (either `self.log` or stripped `log`)
        base = attr.value
        is_log = (isinstance(base, cst.Name) and base.value == "log") or (
            isinstance(base, cst.Attribute)
            and isinstance(base.attr, cst.Name)
            and base.attr.value == "log")
        if not is_log:
            return updated_node
        new_func = cst.Attribute(
            value=cst.Name("logger"),
            attr=cst.Name(_LOG_LEVEL_MAP[level_name]))
        return updated_node.with_changes(func=new_func)


# --- 9. self.PublishResult() → results.publish() + TODO -----------------------

class ConvertPublishResult(cst.CSTTransformer):
    """Replace ``PublishResult()`` calls with a ``results.publish()`` stub + TODO."""

    def __init__(self) -> None:
        super().__init__()

    def leave_SimpleStatementLine(
            self, original_node: cst.SimpleStatementLine,
            updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine:
        new_body: list[cst.BaseSmallStatement] = []
        replaced_here = False
        for stmt in updated_node.body:
            replacement = self._maybe_replace(stmt)
            if replacement is not None:
                replaced_here = True
                new_body.append(replacement)
            else:
                new_body.append(stmt)
        if not replaced_here:
            return updated_node
        comment = cst.Comment(
            "# TODO[openflow-migrate]: choose which out_* values to publish")
        trailing = cst.TrailingWhitespace(
            whitespace=cst.SimpleWhitespace("  "),
            comment=comment,
            newline=cst.Newline())
        return updated_node.with_changes(body=tuple(new_body),
                                         trailing_whitespace=trailing)

    def _maybe_replace(self, stmt: cst.BaseSmallStatement) -> cst.BaseSmallStatement | None:
        if not isinstance(stmt, cst.Expr) or not isinstance(stmt.value, cst.Call):
            return None
        call = stmt.value
        name: str | None = None
        if isinstance(call.func, cst.Name):
            name = call.func.value
        elif isinstance(call.func, cst.Attribute) and isinstance(call.func.attr, cst.Name):
            name = call.func.attr.value
        if name != "PublishResult":
            return None
        new_call = cst.Call(
            func=cst.Attribute(value=cst.Name("results"), attr=cst.Name("publish")),
            args=(),
        )
        return cst.Expr(value=new_call)


# --- 10. Strip trivial lifecycle stubs (__init__, PreRun, PostRun) ------------

_LIFECYCLE_METHODS = {"__init__", "PreRun", "PostRun"}


class StripLifecycleStubs(cst.CSTTransformer):
    """Remove __init__, PreRun, PostRun methods whose body is just `super().X()` or `pass`."""

    def leave_ClassDef(self, original_node: cst.ClassDef,
                       updated_node: cst.ClassDef) -> cst.ClassDef:
        new_body: list[cst.BaseStatement] = []
        for stmt in updated_node.body.body:
            if isinstance(stmt, cst.FunctionDef) and stmt.name.value in _LIFECYCLE_METHODS:
                if self._is_trivial(stmt):
                    continue
            new_body.append(stmt)
        return updated_node.with_changes(
            body=updated_node.body.with_changes(body=tuple(new_body)))

    @staticmethod
    def _is_trivial(func: cst.FunctionDef) -> bool:
        statements = func.body.body
        if not statements:
            return True
        for stmt in statements:
            if isinstance(stmt, cst.SimpleStatementLine):
                for sub in stmt.body:
                    if isinstance(sub, cst.Pass):
                        continue
                    if isinstance(sub, cst.Expr) and isinstance(sub.value, cst.Call):
                        call = sub.value
                        # super().Something()
                        if (isinstance(call.func, cst.Attribute)
                                and isinstance(call.func.value, cst.Call)
                                and isinstance(call.func.value.func, cst.Name)
                                and call.func.value.func.value == "super"):
                            continue
                    return False
            else:
                return False
        return True


# --- 11. Rewrite UMT/U300_RFEngine imports → openflow imports -----------------

# Maps source module path → (target module path, optional rename for the symbol).
# If the rename is the same as the source symbol name, no rename is applied;
# only the module path is rewritten.
_IMPORT_REWRITES: dict[str, tuple[str, dict[str, str]]] = {
    "UMT_Instruments.CMW100":          ("openflow.instruments.cmw100",          {}),
    "UMT_Instruments.WFG":             ("openflow.instruments.stubs",           {}),
    "UMT_Instruments.DMM":             ("openflow.instruments.stubs",           {}),
    "UMT_Instruments.PSU":             ("openflow.instruments.stubs",           {}),
    "UMT_Instruments.OSC":             ("openflow.instruments.stubs",           {}),
    "UMT_Instruments.SG":              ("openflow.instruments.stubs",           {}),
    "UMT_Instruments.SA":              ("openflow.instruments.stubs",           {}),
    "UMT_DUTs.UMT_DUT":                ("openflow.dut.base",                    {"UMT_DUT": "Dut"}),
    "U300_RFEngine.Deembedding":       ("openflow.rfengine.deembedding",        {}),
    "U300_RFEngine.Testconditions_Limits": ("openflow.rfengine.testconditions_limits", {}),
    "U300_RFEngine.Calibration_File":  ("openflow.rfengine.calibration_file",   {}),
}

# Imports that should be removed entirely — no openflow equivalent in V1a.
# Match by full dotted module path; relative imports like `.U300_RFEngine_EVT_Base`
# are matched by the leaf name.
_IMPORTS_TO_DROP: set[str] = {
    "U300_RFEngine.U300_RFEngine_EVT_Base",
    "U300_RFEngine_EVT_Base",  # relative-import form
    "UMT_Base.UMT_TestCase",
}


def _module_path_string(node: cst.Attribute | cst.Name) -> str:
    """Convert an Attribute chain to its dotted string form."""
    parts: list[str] = []
    cur: cst.BaseExpression = node
    while isinstance(cur, cst.Attribute):
        if isinstance(cur.attr, cst.Name):
            parts.append(cur.attr.value)
        cur = cur.value
    if isinstance(cur, cst.Name):
        parts.append(cur.value)
    return ".".join(reversed(parts))


class RewriteImportPaths(cst.CSTTransformer):
    """Rewrite `from UMT_X.Y import Z` → `from openflow.x.y import Z` (or drop entirely)."""

    def leave_SimpleStatementLine(
            self, original_node: cst.SimpleStatementLine,
            updated_node: cst.SimpleStatementLine
    ) -> cst.SimpleStatementLine | cst.RemovalSentinel:
        new_body: list[cst.BaseSmallStatement] = []
        for stmt in updated_node.body:
            if isinstance(stmt, cst.ImportFrom):
                replacement = self._rewrite_import_from(stmt)
                if replacement is None:
                    # Drop entirely
                    continue
                new_body.append(replacement)
            else:
                new_body.append(stmt)
        if not new_body:
            return cst.RemovalSentinel.REMOVE
        return updated_node.with_changes(body=tuple(new_body))

    @staticmethod
    def _rewrite_import_from(node: cst.ImportFrom) -> cst.ImportFrom | None:
        if node.module is None:
            # Relative import like `from .X import Y` — check the names
            if isinstance(node.names, cst.ImportStar):
                return node
            for alias in node.names:
                name = alias.name.value if isinstance(alias.name, cst.Name) else ""
                if name in _IMPORTS_TO_DROP:
                    return None  # drop
            return node

        module_path = _module_path_string(node.module)
        if module_path in _IMPORTS_TO_DROP:
            return None  # drop

        if module_path in _IMPORT_REWRITES:
            new_path, rename_map = _IMPORT_REWRITES[module_path]
            # Build new module attribute chain from the dotted string.
            new_module = RewriteImportPaths._build_module_attribute(new_path)
            # Apply symbol renames if any.
            if rename_map and not isinstance(node.names, cst.ImportStar):
                new_aliases = []
                for alias in node.names:
                    orig = alias.name.value if isinstance(alias.name, cst.Name) else ""
                    if orig in rename_map:
                        new_aliases.append(alias.with_changes(name=cst.Name(rename_map[orig])))
                    else:
                        new_aliases.append(alias)
                return node.with_changes(module=new_module, names=tuple(new_aliases))
            return node.with_changes(module=new_module)
        return node

    @staticmethod
    def _build_module_attribute(dotted: str) -> cst.Attribute | cst.Name:
        parts = dotted.split(".")
        node: cst.Attribute | cst.Name = cst.Name(parts[0])
        for p in parts[1:]:
            node = cst.Attribute(value=node, attr=cst.Name(p))
        return node


# --- 12. Bare `except:` → `except Exception:` --------------------------------

class StripBareExcept(cst.CSTTransformer):
    """Convert bare `except:` clauses to `except Exception:` (PEP-8 best practice)."""

    def leave_ExceptHandler(self, original_node: cst.ExceptHandler,
                            updated_node: cst.ExceptHandler) -> cst.ExceptHandler:
        if updated_node.type is not None:
            return updated_node
        return updated_node.with_changes(
            type=cst.Name("Exception"),
            whitespace_after_except=cst.SimpleWhitespace(" "),
        )


# --- 13. Add `import logging` + `logger = logging.getLogger(__name__)` -------

class AddLoggingHeader(cst.CSTTransformer):
    """If the module contains any `logger.<level>(...)` calls but no logger setup,
    inject the standard ``import logging`` + ``logger = logging.getLogger(__name__)``
    near the top of the module (after existing imports / __dunder__ metadata)."""

    def __init__(self) -> None:
        super().__init__()
        self._has_logger_calls = False
        self._has_logger_assignment = False
        self._has_logging_import = False

    def visit_Call(self, node: cst.Call) -> None:
        # Detect `logger.<anything>(...)` calls.
        func = node.func
        if (isinstance(func, cst.Attribute)
                and isinstance(func.value, cst.Name)
                and func.value.value == "logger"):
            self._has_logger_calls = True

    def visit_Assign(self, node: cst.Assign) -> None:
        # Detect `logger = ...` at any level.
        for target in node.targets:
            if isinstance(target.target, cst.Name) and target.target.value == "logger":
                self._has_logger_assignment = True

    def visit_Import(self, node: cst.Import) -> None:
        for alias in node.names:
            if isinstance(alias.name, cst.Name) and alias.name.value == "logging":
                self._has_logging_import = True

    def leave_Module(self, original_node: cst.Module,
                     updated_node: cst.Module) -> cst.Module:
        if not self._has_logger_calls:
            return updated_node
        if self._has_logger_assignment and self._has_logging_import:
            return updated_node

        new_stmts: list[cst.BaseStatement] = []
        if not self._has_logging_import:
            new_stmts.append(cst.parse_statement("import logging\n"))
        if not self._has_logger_assignment:
            new_stmts.append(cst.parse_statement("logger = logging.getLogger(__name__)\n"))

        body = list(updated_node.body)
        insert_at = self._first_non_metadata_index(body)
        for offset, stmt in enumerate(new_stmts):
            body.insert(insert_at + offset, stmt)
        return updated_node.with_changes(body=tuple(body))

    @staticmethod
    def _first_non_metadata_index(body: list[cst.BaseStatement]) -> int:
        """Find first index past module docstring + existing imports + __dunder__ metadata."""
        for i, stmt in enumerate(body):
            if isinstance(stmt, cst.SimpleStatementLine):
                # All-imports line stays in the metadata region.
                if all(isinstance(s, (cst.Import, cst.ImportFrom)) for s in stmt.body):
                    continue
                first = stmt.body[0] if stmt.body else None
                if isinstance(first, cst.Expr) and isinstance(first.value, cst.SimpleString):
                    continue  # docstring
                if isinstance(first, cst.Assign) and len(first.targets) == 1:
                    t = first.targets[0].target
                    if isinstance(t, cst.Name) and t.value.startswith("__"):
                        continue  # __author__, __version__, etc.
            return i
        return len(body)


# --- 14. Bare `in_X` (read) → `config.X` (after self-strip) ------------------

class RewriteInputAttrs(cst.CSTTransformer):
    """Rewrite bare reads of `in_<name>` to `config.<name>`.

    Skips:
    - The target of an assignment (`in_band = X` — defines a local, not a read).
    - Any function where `in_<name>` is locally bound (assigned anywhere
      in the function body).

    Runs AFTER ConvertClassToTestFunction which strips `self.` prefixes.
    """

    def __init__(self) -> None:
        super().__init__()
        # Stack of sets — locally-bound `in_*` names per nested function scope.
        self._local_in_names_stack: list[set[str]] = [set()]
        # Track assignment-target positions so leave_Name knows to skip them.
        self._assignment_target_ids: set[int] = set()
        # Track kwarg-keyword Name node ids — the LHS of '=' in a call kwarg
        # must stay a bare Name (Attribute is invalid syntax there).
        self._kwarg_keyword_ids: set[int] = set()

    def visit_Arg(self, node: cst.Arg) -> None:
        # Don't rewrite the keyword Name of a kwarg call (e.g. f(in_band=X)).
        if isinstance(node.keyword, cst.Name):
            self._kwarg_keyword_ids.add(id(node.keyword))

    # Track scope: enter a function, push a new set of local names.
    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        local_in: set[str] = set()
        # Find all `in_*` names assigned anywhere in the function body.
        for n in cst.matchers.findall(
                node,
                cst.matchers.Assign(targets=[cst.matchers.AssignTarget(
                    target=cst.matchers.Name())])):
            for tgt in n.targets:
                t = tgt.target
                if isinstance(t, cst.Name) and t.value.startswith("in_"):
                    local_in.add(t.value)
        self._local_in_names_stack.append(local_in)

    def leave_FunctionDef(self, original_node: cst.FunctionDef,
                          updated_node: cst.FunctionDef) -> cst.FunctionDef:
        self._local_in_names_stack.pop()
        return updated_node

    # Track assignment targets so we don't rewrite them.
    def visit_Assign(self, node: cst.Assign) -> None:
        for target in node.targets:
            self._mark_target(target.target)

    def _mark_target(self, node: cst.CSTNode) -> None:
        # Mark this AST node's identity so leave_Name knows to skip it.
        self._assignment_target_ids.add(id(node))
        # Handle tuple unpacking: (a, b) = ...
        if isinstance(node, (cst.Tuple, cst.List)):
            for elem in node.elements:
                if isinstance(elem, cst.Element):
                    self._mark_target(elem.value)

    def leave_Name(self, original_node: cst.Name,
                   updated_node: cst.Name) -> cst.BaseExpression:
        name = updated_node.value
        if not name.startswith("in_") or name == "in_":
            return updated_node
        # Skip assignment targets.
        if id(original_node) in self._assignment_target_ids:
            return updated_node
        # Skip kwarg keywords (LHS of '=' in a call) — must stay bare Name.
        if id(original_node) in self._kwarg_keyword_ids:
            return updated_node
        # Skip if locally defined in the current scope.
        if self._local_in_names_stack and name in self._local_in_names_stack[-1]:
            return updated_node
        # Rewrite: drop the `in_` prefix, build config.<rest>.
        return cst.Attribute(value=cst.Name("config"), attr=cst.Name(name[3:]))


# --- 15. `results.publish()` (bare) → `results.publish(out_X=out_X, ...)` ----

class RewriteOutputPublish(cst.CSTTransformer):
    """Rewrite bare `results.publish()` calls to forward all `out_*` names
    assigned earlier in the enclosing function body (including nested blocks).

    Python scope rules: variables assigned inside loops/if-blocks persist after
    them, so a `for` loop's `out_a` assignment is visible at any subsequent
    `results.publish()` whether inside or outside the loop. Function definitions
    introduce a new scope — their out_* assignments do NOT leak out.

    Runs after ConvertPublishResult.
    """

    def leave_FunctionDef(self, original_node: cst.FunctionDef,
                          updated_node: cst.FunctionDef) -> cst.FunctionDef:
        # Each function has its own out_names accumulator.
        out_names: list[str] = []
        new_body = self._rewrite_block(updated_node.body, out_names)
        return updated_node.with_changes(body=new_body)

    def _rewrite_block(self, block: cst.IndentedBlock,
                       out_names: list[str]) -> cst.IndentedBlock:
        new_statements: list[cst.BaseStatement] = []
        for stmt in block.body:
            new_stmt = self._rewrite_statement(stmt, out_names)
            new_statements.append(new_stmt)
        return block.with_changes(body=tuple(new_statements))

    def _rewrite_statement(self, stmt: cst.BaseStatement,
                           out_names: list[str]) -> cst.BaseStatement:
        # Simple statement line: collect out_* assignments + rewrite any publish call.
        if isinstance(stmt, cst.SimpleStatementLine):
            for sub in stmt.body:
                if isinstance(sub, cst.Assign):
                    for target in sub.targets:
                        self._collect_target_names(target.target, out_names)
            return self._rewrite_publish_in_statement(stmt, out_names)

        # Compound statements with nested IndentedBlocks — recurse.
        if isinstance(stmt, cst.For):
            new_body = self._rewrite_block(stmt.body, out_names) if isinstance(stmt.body, cst.IndentedBlock) else stmt.body
            new_orelse = (cst.Else(body=self._rewrite_block(stmt.orelse.body, out_names))
                          if stmt.orelse and isinstance(stmt.orelse.body, cst.IndentedBlock)
                          else stmt.orelse)
            return stmt.with_changes(body=new_body, orelse=new_orelse)

        if isinstance(stmt, cst.While):
            new_body = self._rewrite_block(stmt.body, out_names) if isinstance(stmt.body, cst.IndentedBlock) else stmt.body
            new_orelse = (cst.Else(body=self._rewrite_block(stmt.orelse.body, out_names))
                          if stmt.orelse and isinstance(stmt.orelse.body, cst.IndentedBlock)
                          else stmt.orelse)
            return stmt.with_changes(body=new_body, orelse=new_orelse)

        if isinstance(stmt, cst.If):
            new_body = self._rewrite_block(stmt.body, out_names) if isinstance(stmt.body, cst.IndentedBlock) else stmt.body
            new_orelse = self._rewrite_if_orelse(stmt.orelse, out_names) if stmt.orelse else None
            return stmt.with_changes(body=new_body, orelse=new_orelse)

        if isinstance(stmt, cst.Try):
            new_body = self._rewrite_block(stmt.body, out_names) if isinstance(stmt.body, cst.IndentedBlock) else stmt.body
            new_handlers = tuple(
                h.with_changes(body=self._rewrite_block(h.body, out_names))
                if isinstance(h.body, cst.IndentedBlock) else h
                for h in stmt.handlers
            )
            new_orelse = (cst.Else(body=self._rewrite_block(stmt.orelse.body, out_names))
                          if stmt.orelse and isinstance(stmt.orelse.body, cst.IndentedBlock)
                          else stmt.orelse)
            new_finally = (cst.Finally(body=self._rewrite_block(stmt.finalbody.body, out_names))
                           if stmt.finalbody and isinstance(stmt.finalbody.body, cst.IndentedBlock)
                           else stmt.finalbody)
            return stmt.with_changes(body=new_body, handlers=new_handlers,
                                     orelse=new_orelse, finalbody=new_finally)

        if isinstance(stmt, cst.With):
            new_body = self._rewrite_block(stmt.body, out_names) if isinstance(stmt.body, cst.IndentedBlock) else stmt.body
            return stmt.with_changes(body=new_body)

        if isinstance(stmt, cst.FunctionDef):
            # Nested function: NEW scope. Its out_* assignments do not leak.
            nested_out_names: list[str] = []
            new_body = self._rewrite_block(stmt.body, nested_out_names)
            return stmt.with_changes(body=new_body)

        # ClassDef and other compound statements: leave alone for now.
        return stmt

    def _rewrite_if_orelse(self, orelse: cst.Else | cst.If | None,
                            out_names: list[str]) -> cst.Else | cst.If | None:
        if orelse is None:
            return None
        if isinstance(orelse, cst.If):
            # elif chain — treat as another If.
            return self._rewrite_statement(orelse, out_names)  # type: ignore[return-value]
        if isinstance(orelse, cst.Else):
            if isinstance(orelse.body, cst.IndentedBlock):
                return cst.Else(body=self._rewrite_block(orelse.body, out_names))
        return orelse

    def _collect_target_names(self, target: cst.CSTNode,
                              out_names: list[str]) -> None:
        if isinstance(target, cst.Name):
            if target.value.startswith("out_") and target.value not in out_names:
                out_names.append(target.value)
        elif isinstance(target, (cst.Tuple, cst.List)):
            for elem in target.elements:
                if isinstance(elem, cst.Element):
                    self._collect_target_names(elem.value, out_names)

    def _rewrite_publish_in_statement(self, stmt: cst.SimpleStatementLine,
                                      out_names: list[str]) -> cst.SimpleStatementLine:
        new_body: list[cst.BaseSmallStatement] = []
        for sub in stmt.body:
            replacement = self._maybe_rewrite_publish_call(sub, out_names)
            new_body.append(replacement if replacement is not None else sub)
        return stmt.with_changes(body=tuple(new_body))

    def _maybe_rewrite_publish_call(self, sub: cst.BaseSmallStatement,
                                    out_names: list[str]
                                    ) -> cst.BaseSmallStatement | None:
        if not isinstance(sub, cst.Expr) or not isinstance(sub.value, cst.Call):
            return None
        call = sub.value
        func = call.func
        if not (isinstance(func, cst.Attribute)
                and isinstance(func.value, cst.Name)
                and func.value.value == "results"
                and isinstance(func.attr, cst.Name)
                and func.attr.value == "publish"):
            return None
        if call.args:
            return None
        if not out_names:
            return None
        new_args = tuple(
            cst.Arg(
                value=cst.Name(name),
                keyword=cst.Name(name),
                equal=cst.AssignEqual(
                    whitespace_before=cst.SimpleWhitespace(""),
                    whitespace_after=cst.SimpleWhitespace("")),
                comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))
                if i < len(out_names) - 1 else cst.MaybeSentinel.DEFAULT,
            )
            for i, name in enumerate(out_names)
        )
        return cst.Expr(value=call.with_changes(args=new_args))


# --- 16. Board serials (RFEB_SN / RFHB_SN) → config.rfeb_sn / config.rfhb_sn -

_BOARD_SERIAL_MAP = {
    "RFEB_SN": "rfeb_sn",
    "RFHB_SN": "rfhb_sn",
}


class RewriteBoardSerials(cst.CSTTransformer):
    """Rewrite bare reads of RFEB_SN / RFHB_SN to config.rfeb_sn / config.rfhb_sn.

    Skips assignment targets (`RFEB_SN = 'X'` defines a local).

    Runs AFTER ConvertClassToTestFunction which strips `self.` prefixes.
    Requires OpenFlowConfig to have `rfeb_sn` and `rfhb_sn` fields at runtime
    (added in V1c-6).
    """

    def __init__(self) -> None:
        super().__init__()
        self._assignment_target_ids: set[int] = set()
        # Track kwarg-keyword Name node ids — the LHS of '=' in a call kwarg
        # must stay a bare Name (Attribute is invalid syntax there).
        self._kwarg_keyword_ids: set[int] = set()

    def visit_Arg(self, node: cst.Arg) -> None:
        # Don't rewrite the keyword Name of a kwarg call (e.g. f(RFEB_SN=X)).
        if isinstance(node.keyword, cst.Name):
            self._kwarg_keyword_ids.add(id(node.keyword))

    def visit_Assign(self, node: cst.Assign) -> None:
        for target in node.targets:
            self._mark_target(target.target)

    def _mark_target(self, node: cst.CSTNode) -> None:
        self._assignment_target_ids.add(id(node))
        if isinstance(node, (cst.Tuple, cst.List)):
            for elem in node.elements:
                if isinstance(elem, cst.Element):
                    self._mark_target(elem.value)

    def leave_Name(self, original_node: cst.Name,
                   updated_node: cst.Name) -> cst.BaseExpression:
        name = updated_node.value
        if name not in _BOARD_SERIAL_MAP:
            return updated_node
        if id(original_node) in self._assignment_target_ids:
            return updated_node
        # Skip kwarg keywords (LHS of '=' in a call) — must stay bare Name.
        if id(original_node) in self._kwarg_keyword_ids:
            return updated_node
        return cst.Attribute(
            value=cst.Name("config"),
            attr=cst.Name(_BOARD_SERIAL_MAP[name]),
        )


# --- 17. Rename legacy config.<old_input_name> → config.<new_field_name> ----

# OpenTAP input properties for file-path inputs used names ending in `_config`.
# OpenFlowConfig (pydantic) uses `<thing>_path` for the same fields. This map
# is the surface where the two naming conventions meet.
#
# Add a new entry whenever a *_config input name shows up in a migrated test
# that should map to a different OpenFlowConfig field.
_CONFIG_NAME_MAP: dict[str, str] = {
    "conditions_limits_config": "limits_path",
    "deembedding_config": "deembedding_path",
    "calibration_file_config": "calibration_path",
}


class RewriteConfigNames(cst.CSTTransformer):
    """Rewrite ``config.<old_name>`` → ``config.<new_name>`` for the inputs
    whose OpenTAP-Python name differs from the OpenFlowConfig field name.

    Runs AFTER RewriteInputAttrs (which is what creates ``config.<X>``
    attribute access in the first place from bare ``in_X`` reads). Order
    inside the pipeline: RewriteInputAttrs → RewriteConfigNames → ...

    Only rewrites Attribute nodes whose value is exactly the Name "config" —
    so ``obj.deembedding_config`` and ``self.calibration_file_config`` are
    left alone.
    """

    def leave_Attribute(self, original_node: cst.Attribute,
                        updated_node: cst.Attribute) -> cst.BaseExpression:
        # Only touch `config.<X>` (i.e. .value is a bare Name == "config").
        if not (isinstance(updated_node.value, cst.Name)
                and updated_node.value.value == "config"):
            return updated_node
        old = updated_node.attr.value
        new = _CONFIG_NAME_MAP.get(old)
        if new is None:
            return updated_node
        return updated_node.with_changes(attr=cst.Name(new))


# --- 18. Capture original class name (Phase 1 metadata only) ----------------

class CaptureClassName(cst.CSTTransformer):
    """Metadata-only Phase 1 transformer. Records the original OpenTAP
    TestStep class name so ``RewriteClassDunderName`` can emit a
    module-level ``CLASS_NAME`` constant in Phase 2.

    Does not modify the tree.

    Captures the *first* class declaration seen — every OpenTAP-Python
    TestStep file we've encountered defines exactly one TestStep class.
    """

    def __init__(self) -> None:
        super().__init__()
        self.class_name: str | None = None

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        if self.class_name is None:
            self.class_name = node.name.value
        return True


# --- 19. __class__.__name__ → CLASS_NAME constant ---------------------------

class RewriteClassDunderName(cst.CSTTransformer):
    """Rewrite ``__class__.__name__`` to a bare ``CLASS_NAME`` Name and
    inject a module-level ``CLASS_NAME = \"<OriginalClass>\"`` assignment
    if any rewrite happened.

    Background: OpenTAP TestStep ``Run()`` methods commonly call
    ``self.__class__.__name__`` to look up their test ID in a conditions
    table. After ConvertClassToTestFunction strips both the class and
    the ``self.`` prefix, what's left is a bare ``__class__.__name__``
    reference inside a module-level function — which is a NameError at
    runtime (the implicit ``__class__`` cell only exists inside class
    methods).

    The original class name is captured during Phase 1 by
    ``CaptureClassName`` and passed in via the constructor. If
    ``class_name`` is ``None`` (no class was seen in the source), this
    transformer no-ops and leaves the dunder in place — the engineer
    will see the NameError and can investigate.

    Pipeline position: Phase 2, after ConvertClassToTestFunction.
    """

    def __init__(self, class_name: str | None) -> None:
        super().__init__()
        self.class_name = class_name
        self._rewrites_happened = False

    def leave_Attribute(self, original_node: cst.Attribute,
                        updated_node: cst.Attribute) -> cst.BaseExpression:
        if self.class_name is None:
            return updated_node
        # Match `__class__.__name__`: Attribute(value=Name("__class__"),
        # attr=Name("__name__")).
        if not (isinstance(updated_node.value, cst.Name)
                and updated_node.value.value == "__class__"
                and updated_node.attr.value == "__name__"):
            return updated_node
        self._rewrites_happened = True
        return cst.Name("CLASS_NAME")

    def leave_Module(self, original_node: cst.Module,
                     updated_node: cst.Module) -> cst.Module:
        if not self._rewrites_happened or self.class_name is None:
            return updated_node
        # Inject `CLASS_NAME = "<OriginalClass>"` after existing imports +
        # __dunder__ metadata.
        const_stmt = cst.parse_statement(
            f'CLASS_NAME = "{self.class_name}"\n')
        body = list(updated_node.body)
        insert_at = self._first_non_metadata_index(body)
        body.insert(insert_at, const_stmt)
        return updated_node.with_changes(body=tuple(body))

    @staticmethod
    def _first_non_metadata_index(body: list[cst.BaseStatement]) -> int:
        """Find first index past module docstring + existing imports + __dunder__ metadata."""
        for i, stmt in enumerate(body):
            if isinstance(stmt, cst.SimpleStatementLine):
                if all(isinstance(s, (cst.Import, cst.ImportFrom)) for s in stmt.body):
                    continue
                first = stmt.body[0] if stmt.body else None
                if isinstance(first, cst.Expr) and isinstance(first.value, cst.SimpleString):
                    continue  # docstring
                if isinstance(first, cst.Assign) and len(first.targets) == 1:
                    t = first.targets[0].target
                    if isinstance(t, cst.Name) and t.value.startswith("__"):
                        continue  # __author__, __version__, etc.
            return i
        return len(body)


# --- 20. Setup_DMM/Get_DMM/Get_Aux → lowercase + auto-import ----------------

# OpenTAP CamelCase helper -> (new lowercase name, default arg-fill).
# The arg-fill is what we emit when the call has no args (the common case).
# `dmms={}` makes the call runtime-safe (no TypeError on required param) but
# returns nothing — engineer fills in their bench's DMM mapping.
_EVT_HELPER_MAP: dict[str, tuple[str, str]] = {
    "Setup_DMM": ("setup_dmm", "dmms={}"),
    "Get_DMM":   ("get_dmm",   "dmms={}"),
    "Get_Aux":   ("get_aux",   "dut"),
}


class RewriteEvtHelperCalls(cst.CSTTransformer):
    """Rewrite bare-name calls to the OpenTAP EVT-base helpers into their
    module-level Python equivalents from ``openflow.rfengine.evt_base``,
    and inject the corresponding ``from ... import ...`` statement for
    the helpers actually used.

    Before  (after ConvertClassToTestFunction has stripped ``self.``):
        Setup_DMM()
        Get_DMM()
        Get_Aux()

    After:
        from openflow.rfengine.evt_base import setup_dmm, get_dmm, get_aux
        ...
        setup_dmm(dmms={})           # engineer fills in their DMM dict
        get_dmm(dmms={})
        get_aux(dut)

    Behavior notes:

    * Bare-name calls only — ``obj.Setup_DMM()`` is left alone (could be a
      real method on a different object).
    * Calls that already have explicit args (``Setup_DMM(dmms={...})``)
      are renamed but their args are preserved.
    * Imports that already exist (engineer pre-imported) are not duplicated.
    * Pipeline position: after ConvertClassToTestFunction (which strips
      ``self.``) and after the other Phase-2 rewrites that build the test
      function body.
    """

    def __init__(self) -> None:
        super().__init__()
        # Lowercase names actually emitted into the rewritten tree.
        self._used: set[str] = set()
        # Already-imported names from evt_base (so we don't re-add).
        self._already_imported: set[str] = set()

    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        # Detect `from openflow.rfengine.evt_base import setup_dmm, ...`
        module = node.module
        if not isinstance(module, cst.Attribute):
            return
        # Build the dotted-name string.
        if self._dotted_name(module) != "openflow.rfengine.evt_base":
            return
        if isinstance(node.names, cst.ImportStar):
            # `from ... import *` — assume everything is in scope.
            self._already_imported.update(new for new, _ in _EVT_HELPER_MAP.values())
            return
        for alias in node.names:
            if isinstance(alias.name, cst.Name):
                self._already_imported.add(alias.name.value)

    @staticmethod
    def _dotted_name(node: cst.BaseExpression) -> str:
        parts: list[str] = []
        while isinstance(node, cst.Attribute):
            parts.append(node.attr.value)
            node = node.value
        if isinstance(node, cst.Name):
            parts.append(node.value)
        return ".".join(reversed(parts))

    def leave_Call(self, original_node: cst.Call,
                   updated_node: cst.Call) -> cst.BaseExpression:
        # Match bare-name calls only: func must be a Name, not Attribute.
        if not isinstance(updated_node.func, cst.Name):
            return updated_node
        old = updated_node.func.value
        entry = _EVT_HELPER_MAP.get(old)
        if entry is None:
            return updated_node
        new_name, default_arg = entry
        self._used.add(new_name)
        # If the call already has args, preserve them; just rename.
        if updated_node.args:
            return updated_node.with_changes(func=cst.Name(new_name))
        # No args — inject the default placeholder.
        placeholder_call = cst.parse_expression(f"{new_name}({default_arg})")
        return placeholder_call

    def leave_Module(self, original_node: cst.Module,
                     updated_node: cst.Module) -> cst.Module:
        to_import = self._used - self._already_imported
        if not to_import:
            return updated_node
        # Stable ordering for reproducible output.
        names = sorted(to_import)
        import_line = (
            "from openflow.rfengine.evt_base import "
            + ", ".join(names) + "\n"
        )
        import_stmt = cst.parse_statement(import_line)
        body = list(updated_node.body)
        insert_at = self._first_non_metadata_index(body)
        body.insert(insert_at, import_stmt)
        return updated_node.with_changes(body=tuple(body))

    @staticmethod
    def _first_non_metadata_index(body: list[cst.BaseStatement]) -> int:
        """Same heuristic as AddLoggingHeader / RewriteClassDunderName:
        skip module docstring, existing imports, and __dunder__ metadata."""
        for i, stmt in enumerate(body):
            if isinstance(stmt, cst.SimpleStatementLine):
                if all(isinstance(s, (cst.Import, cst.ImportFrom)) for s in stmt.body):
                    continue
                first = stmt.body[0] if stmt.body else None
                if isinstance(first, cst.Expr) and isinstance(first.value, cst.SimpleString):
                    continue
                if isinstance(first, cst.Assign) and len(first.targets) == 1:
                    t = first.targets[0].target
                    if isinstance(t, cst.Name) and t.value.startswith("__"):
                        continue
            return i
        return len(body)


# --- 21. for x in iterable: ... → @pytest.mark.parametrize -----------------

# Instrument-fixture object names that, when called as `<name>.method()` inside
# a loop body, signal "this loop has per-iteration setup side effects —
# don't lift". Keep this list narrow so we only veto on real instrument calls,
# not on e.g. `results.publish(...)` which is exactly what parametrize cases do.
_INSTRUMENT_FIXTURE_NAMES: set[str] = {
    "dut", "cmw100", "wfg", "sg", "sa", "dmm_c", "dmm_v", "psu", "osc",
}


class RewriteSweepLoops(cst.CSTTransformer):
    """Lift simple outer ``for x in iterable:`` loops into
    ``@pytest.mark.parametrize`` decorators.

    Conservative heuristic — only lifts loops that:

    1. Live directly inside the body of a ``def test_*`` function
       (one level deep — no nested-loop or if-inside-function cases).
    2. Have an iterable that is a literal list/tuple, a ``range(...)``
       call, or a ``np.arange(...)`` call. Other iterables (computed
       lists, generator expressions, attribute accesses) are
       left alone — they may have side effects we can't infer.
    3. Have a body where every statement is either:
       - a ``results.publish(...)`` call, OR
       - an ``assert ...``, OR
       - a pure assignment that doesn't reference instrument fixtures
       …and crucially, **no** statement calls a method on an
       instrument-fixture object (see ``_INSTRUMENT_FIXTURE_NAMES``).
    4. Are the **first** liftable loop in the function (multiple-loop
       cases stay manual to avoid surprising cartesian-product behavior).

    When the heuristic matches, the transformer:

    - Adds the loop variable to the function's parameter list.
    - Prepends ``@pytest.mark.parametrize("<var>", <iterable>)`` to
      the function's decorator stack.
    - Replaces the loop with its body (unindented one level).
    """

    def leave_FunctionDef(self, original_node: cst.FunctionDef,
                          updated_node: cst.FunctionDef) -> cst.CSTNode:
        if not updated_node.name.value.startswith("test_"):
            return updated_node

        body = list(updated_node.body.body)
        for idx, stmt in enumerate(body):
            if not isinstance(stmt, cst.For):
                continue
            lift = self._try_lift(stmt)
            if lift is None:
                continue
            loop_var, iterable_expr, new_body_statements = lift

            new_function_body = body[:idx] + new_body_statements + body[idx + 1:]
            new_indented_block = updated_node.body.with_changes(
                body=tuple(new_function_body))

            new_params = updated_node.params.with_changes(
                params=(*updated_node.params.params,
                        cst.Param(name=cst.Name(loop_var))))

            parametrize_decorator = cst.Decorator(
                decorator=cst.parse_expression(
                    f"pytest.mark.parametrize({loop_var!r}, "
                    f"{self._render_iterable(iterable_expr)})"))
            new_decorators = (parametrize_decorator, *updated_node.decorators)

            return updated_node.with_changes(
                body=new_indented_block,
                params=new_params,
                decorators=new_decorators)

        return updated_node

    @staticmethod
    def _render_iterable(node: cst.BaseExpression) -> str:
        return cst.Module(body=[]).code_for_node(node)

    def _try_lift(self, for_node: cst.For
                  ) -> tuple[str, cst.BaseExpression, list[cst.BaseStatement]] | None:
        if not isinstance(for_node.target, cst.Name):
            return None
        loop_var = for_node.target.value
        if not self._is_pure_iterable(for_node.iter):
            return None
        if not isinstance(for_node.body, cst.IndentedBlock):
            return None
        for stmt in for_node.body.body:
            if not self._is_liftable_statement(stmt):
                return None
        return loop_var, for_node.iter, list(for_node.body.body)

    @staticmethod
    def _is_pure_iterable(node: cst.BaseExpression) -> bool:
        if isinstance(node, (cst.List, cst.Tuple)):
            return True
        if isinstance(node, cst.Call):
            func = node.func
            if isinstance(func, cst.Name) and func.value == "range":
                return True
            if (isinstance(func, cst.Attribute)
                    and isinstance(func.value, cst.Name)
                    and func.value.value == "np"
                    and func.attr.value == "arange"):
                return True
        return False

    def _is_liftable_statement(self, stmt: cst.BaseStatement) -> bool:
        if isinstance(stmt, (cst.For, cst.While, cst.Try, cst.With, cst.If)):
            return False
        for call in cst.matchers.findall(stmt, cst.matchers.Call()):
            if self._is_instrument_method_call(call):
                return False
        # Also veto on plain assignments to non-trivial RHS (e.g. y = x * 2).
        # Allow only result.publish(...) calls + simple `assert ...`.
        if isinstance(stmt, cst.SimpleStatementLine):
            for sub in stmt.body:
                if isinstance(sub, cst.Assign):
                    # Reject any assignment — too easy to break.
                    return False
        return True

    @staticmethod
    def _is_instrument_method_call(call: cst.Call) -> bool:
        func = call.func
        if not isinstance(func, cst.Attribute):
            return False
        receiver = func.value
        if not isinstance(receiver, cst.Name):
            return False
        return receiver.value in _INSTRUMENT_FIXTURE_NAMES


# --- 22. Print_Summary(...) → logger.info(...) ---------------------------

class RewritePrintSummary(cst.CSTTransformer):
    """Rewrite bare-name ``Print_Summary(...)`` calls into ``logger.info(...)``.

    The OpenTAP ``Print_Summary`` helper was a debug-aid log convenience
    on a TestStep base class. After ConvertClassToTestFunction strips
    ``self.`` the call becomes a bare-name reference that would
    NameError at runtime.

    Rewrite preserves the keyword arguments as format-string arguments:

      Print_Summary()                  -> logger.info("Print_Summary")
      Print_Summary(m='QPSK')          -> logger.info("Print_Summary: m=%s", 'QPSK')
      Print_Summary(m='QPSK', p=10)    -> logger.info("Print_Summary: m=%s p=%s", 'QPSK', 10)

    Bare-name only — ``obj.Print_Summary()`` is left alone.

    AddLoggingHeader (transformer #13) already guarantees ``logger`` is
    in scope; this transformer doesn't need to inject an import.
    """

    def leave_Call(self, original_node: cst.Call,
                   updated_node: cst.Call) -> cst.BaseExpression:
        # Bare-name match only.
        if not isinstance(updated_node.func, cst.Name):
            return updated_node
        if updated_node.func.value != "Print_Summary":
            return updated_node

        # Build the format string + value args from the original kwargs.
        kwarg_names: list[str] = []
        value_args: list[cst.Arg] = []
        for arg in updated_node.args:
            if isinstance(arg.keyword, cst.Name):
                kwarg_names.append(arg.keyword.value)
                value_args.append(cst.Arg(value=arg.value))
            # Positional args fall through — Print_Summary in source only
            # took kwargs, but we tolerate the unusual case by passing values
            # through with a generic placeholder.
            else:
                kwarg_names.append("?")
                value_args.append(cst.Arg(value=arg.value))

        if kwarg_names:
            format_str = "Print_Summary: " + " ".join(f"{k}=%s" for k in kwarg_names)
        else:
            format_str = "Print_Summary"

        format_arg = cst.Arg(value=cst.SimpleString(f'"{format_str}"'))
        new_args = (format_arg, *value_args)
        new_func = cst.Attribute(value=cst.Name("logger"), attr=cst.Name("info"))
        return updated_node.with_changes(func=new_func, args=new_args)
