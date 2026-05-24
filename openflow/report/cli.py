"""``openflow report`` CLI — V4.

Subcommands:

    openflow report ingest <file.json> [--db <path>]
    openflow report list-sessions [--db <path>]
    openflow report show <session-id> [--db <path>]
    openflow report query [--where <sql>] [--since <duration>] [--db <path>]
    openflow report trend --test <id> --metric <name> [--since <duration>]
                          [--db <path>] [--plot <path.png>]
    openflow report migrate [--db <path>]

The CLI is exposed via the ``openflow`` console script (see
``pyproject.toml``). Run ``openflow report --help`` for full usage.

``--db`` defaults to ``./report.db`` (the path where the pytest plugin
writes when ``storage.persist: true``).

``--since`` accepts ``Nd`` (days), ``Nh`` (hours), ``Nm`` (minutes),
or raw seconds.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _parse_duration(value: str) -> int:
    """Parse ``Nd`` / ``Nh`` / ``Nm`` / ``Ns`` / raw seconds into seconds."""
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("empty duration")
    suffix = value[-1].lower()
    if suffix in {"d", "h", "m", "s"}:
        try:
            n = int(value[:-1])
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"invalid duration: {value!r}") from exc
        return {"d": 86400, "h": 3600, "m": 60, "s": 1}[suffix] * n
    try:
        return int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"duration must be e.g. '7d', '24h', '90m', '3600' (got {value!r})"
        ) from exc


def _open_backend(db_path: Path) -> SQLiteBackend:
    from openflow.report.db.sqlite_backend import SQLiteBackend
    return SQLiteBackend(db_path)


# Forward declaration so the return-type annotation above resolves.
if False:  # pragma: no cover - typing only
    from openflow.report.db.sqlite_backend import SQLiteBackend


def _format_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Simple ASCII table — no rich dep required for the CLI."""
    if not rows:
        return "(no rows)"
    str_rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(h), *(len(r[i]) for r in str_rows))
              for i, h in enumerate(headers)]
    sep = "  ".join("-" * w for w in widths)
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    out = [line, sep]
    for r in str_rows:
        out.append("  ".join(c.ljust(widths[i]) for i, c in enumerate(r)))
    return "\n".join(out)


# --- subcommands ---------------------------------------------------------

def cmd_ingest(args: argparse.Namespace) -> int:
    backend = _open_backend(args.db)
    backend.ensure_schema()
    for src in args.json_files:
        sid = backend.ingest_json(Path(src))
        print(f"ingested {src} -> session_id={sid}")
    return 0


def cmd_list_sessions(args: argparse.Namespace) -> int:
    backend = _open_backend(args.db)
    backend.ensure_schema()
    sessions = backend.list_sessions()
    if args.json:
        print(json.dumps([_serialize_dt(s) for s in sessions], indent=2))
        return 0
    rows = [
        [s["session_id"], s.get("started_at"), s.get("passed"),
         s.get("failed"), s.get("host") or "-"]
        for s in sessions
    ]
    print(_format_table(
        ["session_id", "started_at", "passed", "failed", "host"], rows))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    backend = _open_backend(args.db)
    backend.ensure_schema()
    s = backend.get_session(args.session_id)
    if s is None:
        print(f"no session: {args.session_id}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(_serialize_dt(s), indent=2))
        return 0
    for k, v in s.items():
        print(f"{k}: {v}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    backend = _open_backend(args.db)
    backend.ensure_schema()
    rows = backend.query_tests(
        where=args.where,
        since_seconds=args.since,
    )
    if args.json:
        print(json.dumps([_serialize_dt(r) for r in rows], indent=2))
        return 0
    if not rows:
        print("(no matching tests)")
        return 0
    table_rows = [
        [r["test_id"], r.get("started_at"), r.get("testcase_id") or "-",
         r.get("verdict") or "-", r.get("test_node_id")]
        for r in rows
    ]
    print(_format_table(
        ["test_id", "started_at", "testcase", "verdict", "node"], table_rows))
    return 0


def cmd_trend(args: argparse.Namespace) -> int:
    backend = _open_backend(args.db)
    backend.ensure_schema()
    points = backend.trend(
        testcase_id=args.test,
        metric=args.metric,
        since_seconds=args.since,
    )
    if args.json:
        print(json.dumps([(ts.isoformat(), v) for ts, v in points], indent=2))
        return 0
    if not points:
        print(f"(no trend data for testcase={args.test} metric={args.metric})")
        return 0
    rows = [[ts.isoformat(), f"{v:.4f}"] for ts, v in points]
    print(_format_table(["started_at", args.metric], rows))

    if args.plot:
        return _emit_plot(args.plot, points, args.test, args.metric)
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    """V4: schema is auto-applied on first open via ``ensure_schema()``.
    This subcommand is a no-op for V4 but exists so future schema
    migrations have an explicit entry-point."""
    backend = _open_backend(args.db)
    backend.ensure_schema()
    version = backend.current_schema_version()
    print(f"schema version: {version} (no pending migrations)")
    return 0


# --- helpers -------------------------------------------------------------

def _serialize_dt(row: dict[str, Any]) -> dict[str, Any]:
    """Recursively convert datetime values to ISO-8601 strings for JSON output."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _emit_plot(plot_path: str, points: list[tuple[datetime, float]],
               testcase: str, metric: str) -> int:
    try:
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        print("matplotlib not installed — re-run with `uv sync --extra plot`",
              file=sys.stderr)
        return 2
    xs = [ts for ts, _ in points]
    ys = [v for _, v in points]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(xs, ys, marker="o")
    ax.set_xlabel("started_at")
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} trend — {testcase}")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(plot_path, dpi=120)
    print(f"plot -> {plot_path}")
    return 0


# --- argparse wiring -----------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openflow report",
        description="V4: query the persistent results database.",
    )
    parser.add_argument("--db", type=Path, default=Path("report.db"),
                        help="Path to the SQLite database (default: ./report.db)")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_ingest = sub.add_parser("ingest",
                              help="Load a V1-V3 report.json into the database")
    p_ingest.add_argument("json_files", nargs="+", type=Path)
    p_ingest.set_defaults(func=cmd_ingest)

    p_list = sub.add_parser("list-sessions", help="List all sessions")
    p_list.add_argument("--json", action="store_true", help="JSON output")
    p_list.set_defaults(func=cmd_list_sessions)

    p_show = sub.add_parser("show", help="Show a single session by ID")
    p_show.add_argument("session_id")
    p_show.add_argument("--json", action="store_true")
    p_show.set_defaults(func=cmd_show)

    p_query = sub.add_parser("query", help="Query tests with optional filters")
    p_query.add_argument("--where", default=None,
                         help="SQL fragment, e.g. \"testcase_id LIKE 'U300%%'\"")
    p_query.add_argument("--since", type=_parse_duration, default=None,
                         help="Filter to recent sessions, e.g. '7d', '24h', '90m'")
    p_query.add_argument("--json", action="store_true")
    p_query.set_defaults(func=cmd_query)

    p_trend = sub.add_parser("trend",
                             help="Show a metric's trend for a testcase over time")
    p_trend.add_argument("--test", required=True,
                         help="testcase_id to trend (e.g. U300B0-RFE-EVT-005)")
    p_trend.add_argument("--metric", required=True,
                         help="Measurement name (e.g. measured_EVM_pct)")
    p_trend.add_argument("--since", type=_parse_duration, default=None)
    p_trend.add_argument("--plot", default=None,
                         help="Write a PNG chart of the trend (requires "
                              "matplotlib, install via `uv sync --extra plot`)")
    p_trend.add_argument("--json", action="store_true")
    p_trend.set_defaults(func=cmd_trend)

    p_migrate = sub.add_parser("migrate", help="Apply pending schema migrations")
    p_migrate.set_defaults(func=cmd_migrate)

    return parser


def cli_main(argv: list[str] | None = None) -> int:
    """Entry point for the ``openflow report ...`` subcommand."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(cli_main())
