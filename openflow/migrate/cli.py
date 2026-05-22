"""`openflow` CLI entry point. Dispatches between sub-CLIs:

  openflow migrate <source>      -- V1-V3 OpenTAP-Python → pytest migrator
  openflow report <subcommand>   -- V4 persistent-results CLI

The ``report`` subcommand is forwarded verbatim to
``openflow.report.cli.cli_main`` to keep its argparse spec self-contained.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from openflow.migrate.pipeline import migrate_source


def main(argv: list[str] | None = None) -> int:
    # We need to peel off the top-level subcommand BEFORE argparse parses
    # the rest, because the `report` subcommand has its own argparse tree
    # and we want to forward sys.argv-style args verbatim.
    argv = list(argv) if argv is not None else sys.argv[1:]
    if argv and argv[0] == "report":
        from openflow.report.cli import cli_main
        return cli_main(argv[1:])
    if argv and argv[0] == "bench":
        from openflow.bench.cli import cli_main as bench_main
        return bench_main(argv[1:])

    parser = argparse.ArgumentParser(
        prog="openflow",
        description="OpenFlow CLI — convert OpenTAP-Python tests to pytest "
                    "tests + query the V4 results database.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    migrate_p = sub.add_parser("migrate",
                               help="Convert an OpenTAP test source file.")
    migrate_p.add_argument("source", type=Path,
                           help="Path to the OpenTAP-Python test file.")
    migrate_p.add_argument("--out", "-o", type=Path, default=None,
                           help="Output path (default: alongside source, prefixed with test_).")
    # Document the report subcommand so `openflow --help` mentions it.
    sub.add_parser("report",
                   help="Query the V4 persistent-results database. "
                        "Run `openflow report --help` for full usage.")
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
