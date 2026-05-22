"""``openflow dashboard serve`` CLI — V5c.

Spawns a uvicorn server hosting the read-only V5c dashboard.

    openflow dashboard serve --db report.db [--host 0.0.0.0] [--port 8080]
                             [--reservations ~/.openflow/reservations.json]
"""
from __future__ import annotations

import argparse
from pathlib import Path


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from openflow.dashboard.server import create_app

    app = create_app(
        db_path=args.db,
        reservations_path=args.reservations,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level=args.log_level)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openflow dashboard",
        description="V5c: read-only web dashboard over the V4 DB + V5a reservations.",
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_serve = sub.add_parser("serve", help="Start the dashboard HTTP server.")
    p_serve.add_argument("--db", type=Path, required=True,
                         help="Path to the V4 SQLite DB.")
    p_serve.add_argument("--reservations", default=None,
                         help="Reservation store path or DSN (default: "
                              "~/.openflow/reservations.json)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)
    p_serve.add_argument("--log-level", default="info",
                         choices=["debug", "info", "warning", "error"])
    p_serve.set_defaults(func=cmd_serve)

    return parser


def cli_main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli_main())
