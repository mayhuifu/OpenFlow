"""libcst transformers that convert an OpenTAP-Python test source into a pytest test."""
from __future__ import annotations

import libcst as cst
from libcst import RemovalSentinel
from libcst import matchers  # noqa: F401


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

import re


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
        fixture_names = list(self.instrument_fixtures) + ["config", "results"]
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
