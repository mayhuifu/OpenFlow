"""``openflow bench`` CLI — V5a.

Subcommands:

    openflow bench reserve --resource <r> --for <duration> [--reason <txt>] [--by <name>]
    openflow bench release --resource <r>
    openflow bench status

``--store`` lets engineers point at either:
  - a JSON file path (local store, FileLock-protected), or
  - a sqlite:// URL or postgresql:// DSN (shared store)

Defaults to ``~/.openflow/reservations.json`` (local).

``--by`` defaults to ``$OPENFLOW_USER`` if set, else ``$USER``.

``--for`` accepts ``Nd`` / ``Nh`` / ``Nm`` / ``Ns`` or raw seconds.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

from openflow.bench.reservation import (
    LocalReservationStore,
    ReservationConflict,
    SharedReservationStore,
)
from openflow.report.cli import _format_table, _parse_duration


def _default_store_path() -> Path:
    return Path.home() / ".openflow" / "reservations.json"


def _default_user() -> str:
    return os.environ.get("OPENFLOW_USER") or os.environ.get("USER") or "unknown"


def _open_store(store_arg: str) -> Any:
    """Build a store from the --store CLI value."""
    if store_arg.startswith(("postgresql", "postgres", "sqlite")):
        return SharedReservationStore(store_arg)
    return LocalReservationStore(Path(store_arg))


def cmd_reserve(args: argparse.Namespace) -> int:
    store = _open_store(args.store)
    try:
        info = store.reserve(
            args.resource, by=args.by,
            duration_s=args.duration,
            reason=args.reason,
        )
    except ReservationConflict as exc:
        print(f"conflict: {exc}", file=sys.stderr)
        return 1
    print(f"reserved {info.resource} for {info.acquired_by} until {info.expires_at.isoformat()}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    store = _open_store(args.store)
    store.release(args.resource)
    print(f"released {args.resource}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    store = _open_store(args.store)
    rows = store.status()
    if not rows:
        print("(no reservations)")
        return 0
    table_rows = [
        [r.resource, r.acquired_by, r.expires_at.isoformat(),
         "expired" if r.is_expired else "active",
         r.reason or "-"]
        for r in rows
    ]
    print(_format_table(
        ["resource", "by", "expires_at", "state", "reason"], table_rows))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openflow bench",
        description="V5a: bench reservation — coordinate multi-engineer lab access.",
    )
    parser.add_argument("--store", default=str(_default_store_path()),
                        help="Reservation store path (default: "
                             "~/.openflow/reservations.json). Use a "
                             "sqlite:// URL or postgresql:// DSN for "
                             "shared multi-bench labs.")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_reserve = sub.add_parser("reserve", help="Reserve a bench resource.")
    p_reserve.add_argument("--resource", required=True)
    p_reserve.add_argument("--for", "--duration", dest="duration",
                           type=_parse_duration, required=True,
                           help="Reservation duration, e.g. '4h', '90m'.")
    p_reserve.add_argument("--reason", default=None)
    p_reserve.add_argument("--by", default=_default_user())
    p_reserve.set_defaults(func=cmd_reserve)

    p_release = sub.add_parser("release", help="Release a reservation.")
    p_release.add_argument("--resource", required=True)
    p_release.set_defaults(func=cmd_release)

    p_status = sub.add_parser("status", help="List active reservations.")
    p_status.set_defaults(func=cmd_status)

    return parser


def cli_main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli_main())
