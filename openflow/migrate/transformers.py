"""libcst transformers that convert an OpenTAP-Python test source into a pytest test."""
from __future__ import annotations

import libcst as cst
from libcst import RemovalSentinel


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
