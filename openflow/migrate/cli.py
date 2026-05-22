"""`openflow migrate` CLI entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openflow.migrate.pipeline import migrate_source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="openflow",
        description="OpenFlow CLI — convert OpenTAP-Python tests to pytest tests.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    migrate_p = sub.add_parser("migrate",
                               help="Convert an OpenTAP test source file.")
    migrate_p.add_argument("source", type=Path,
                           help="Path to the OpenTAP-Python test file.")
    migrate_p.add_argument("--out", "-o", type=Path, default=None,
                           help="Output path (default: alongside source, prefixed with test_).")
    args = parser.parse_args(argv)

    if args.cmd != "migrate":
        parser.print_help()
        return 64

    if not args.source.is_file():
        print(f"error: source not found: {args.source}", file=sys.stderr)
        return 66

    result = migrate_source(args.source.read_text(encoding="utf-8"))
    out = args.out or _default_output_path(args.source)
    out.write_text(result.code, encoding="utf-8")

    print(f"wrote {out}")
    if result.inputs:
        print(f"  {len(result.inputs)} input field(s) need to move to YAML config:")
        for name, default in result.inputs:
            print(f"    - {name} (was: {default})")
    if result.instrument_fixtures:
        print(f"  test signature uses fixtures: {result.instrument_fixtures}")
    print("  PublishResult calls were left bare — pick out_* values to forward to results.publish()")
    return 0


def _default_output_path(source: Path) -> Path:
    stem = source.stem
    if not stem.startswith("test_"):
        stem = "test_" + stem.lower()
    return source.with_name(f"{stem}.py")
