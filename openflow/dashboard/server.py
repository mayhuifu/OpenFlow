"""V5c FastAPI app. Read-only views over the V4 DB + V5a reservations.

Endpoints:

    GET /                           — dashboard home (recent sessions)
    GET /sessions                   — full sessions list
    GET /sessions/{session_id}      — session detail (per-test rows)
    GET /bench                      — active bench reservations
    GET /trends                     — trend query form + results
    GET /api/sessions               — JSON list (for external integrations)
    GET /api/sessions/{id}/tests    — JSON list of tests for a session
    GET /api/bench                  — JSON list of active reservations

Templates use inline CSS (no static asset pipeline). HTMX for the trend
query interaction without a build step.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from openflow.bench.reservation import (
    LocalReservationStore,
    ReservationInfo,
    SharedReservationStore,
)
from openflow.report.db.sqlite_backend import SQLiteBackend

# Embedded CSS — same style as the V2 HTML report (familiar look).
_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       margin: 2rem auto; max-width: 1100px; color: #1a1a1a; padding: 0 1rem; }
h1, h2 { margin: 0 0 0.5rem 0; }
h1 { font-size: 1.5rem; }
h2 { font-size: 1.2rem; margin-top: 2rem; }
nav { margin-bottom: 1.5rem; }
nav a { margin-right: 1rem; color: #1976d2; text-decoration: none; }
nav a:hover { text-decoration: underline; }
table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
th, td { text-align: left; padding: 0.5rem 0.75rem;
         border-bottom: 1px solid #e0e0e0; }
th { background: #fafafa; font-weight: 600; font-size: 0.85rem;
     text-transform: uppercase; color: #666; }
.passed { color: #2e7d32; font-weight: 600; }
.failed { color: #c62828; font-weight: 600; }
.expired { color: #999; }
form { margin: 1rem 0; padding: 1rem; background: #f5f5f5; border-radius: 6px; }
form label { display: inline-block; margin-right: 1rem; }
form input { padding: 0.4rem; }
form button { padding: 0.4rem 1rem; background: #1976d2; color: white;
              border: none; border-radius: 4px; cursor: pointer; }
.empty { color: #999; font-style: italic; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e0e0e0;
         color: #999; font-size: 0.8rem; text-align: center; }
"""


def create_app(db_path: Path | str | None = None,
               reservations_path: Path | str | None = None) -> FastAPI:
    """Build a FastAPI app backed by the V4 DB + V5a reservation store.

    ``db_path`` — path to the V4 SQLite DB.
    ``reservations_path`` — path or DSN for the V5a reservation store.
        If None, falls back to ``~/.openflow/reservations.json``.
    """
    app = FastAPI(title="OpenFlow dashboard")

    db_path_resolved = Path(db_path) if db_path else None

    def _backend() -> SQLiteBackend:
        if db_path_resolved is None or not db_path_resolved.exists():
            raise HTTPException(status_code=503,
                                detail="V4 database not configured / not found")
        return SQLiteBackend(db_path_resolved)

    def _reservation_store() -> Any:
        path: Path | str
        if reservations_path is None:
            from openflow.bench.cli import _default_store_path
            path = _default_store_path()
        else:
            path = reservations_path
        path_str = str(path)
        if path_str.startswith(("postgresql", "postgres", "sqlite")):
            return SharedReservationStore(path_str)
        return LocalReservationStore(path_str)

    # --- HTML endpoints --------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        try:
            sessions = _backend().list_sessions()[:20]
        except HTTPException:
            sessions = []
        return _render_page("Dashboard", _render_session_list(sessions))

    @app.get("/sessions", response_class=HTMLResponse)
    def sessions_list() -> str:
        sessions = _backend().list_sessions()
        return _render_page("All sessions", _render_session_list(sessions))

    @app.get("/sessions/{session_id}", response_class=HTMLResponse)
    def session_detail(session_id: str) -> str:
        backend = _backend()
        session = backend.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"no session: {session_id}")
        tests = backend.query_tests(where=f"tests.session_id = '{session_id}'")
        return _render_page(
            f"Session {session_id}",
            _render_session_detail(session, tests))

    @app.get("/bench", response_class=HTMLResponse)
    def bench() -> str:
        rows = _reservation_store().status()
        return _render_page("Bench reservations", _render_reservations(rows))

    @app.get("/trends", response_class=HTMLResponse)
    def trends(test: str | None = None, metric: str | None = None) -> str:
        body = _render_trend_form(test, metric)
        if test and metric:
            try:
                points = _backend().trend(testcase_id=test, metric=metric)
                body += _render_trend_chart(test, metric, points)
            except HTTPException:
                body += '<p class="empty">DB not available</p>'
        return _render_page("Trends", body)

    # --- JSON endpoints --------------------------------------------------

    @app.get("/api/sessions")
    def api_sessions() -> list[dict[str, Any]]:
        return [_serialize(s) for s in _backend().list_sessions()]

    @app.get("/api/sessions/{session_id}/tests")
    def api_session_tests(session_id: str) -> list[dict[str, Any]]:
        backend = _backend()
        if backend.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail=f"no session: {session_id}")
        return [_serialize(t)
                for t in backend.query_tests(
                    where=f"tests.session_id = '{session_id}'")]

    @app.get("/api/bench")
    def api_bench() -> list[dict[str, Any]]:
        return [r.to_dict() for r in _reservation_store().status()]

    return app


# --- rendering helpers ---------------------------------------------------

def _render_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OpenFlow dashboard — {title}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>OpenFlow dashboard</h1>
<nav>
  <a href="/">Home</a>
  <a href="/sessions">Sessions</a>
  <a href="/bench">Bench</a>
  <a href="/trends">Trends</a>
</nav>
<h2>{title}</h2>
{body}
<footer>OpenFlow V5c — read-only dashboard. No write endpoints exposed.</footer>
</body>
</html>"""


def _render_session_list(sessions: list[dict[str, Any]]) -> str:
    if not sessions:
        return '<p class="empty">no sessions yet</p>'
    rows = []
    for s in sessions:
        sid = s["session_id"]
        rows.append(
            f'<tr><td><a href="/sessions/{sid}">{sid}</a></td>'
            f'<td>{s.get("started_at") or "-"}</td>'
            f'<td class="passed">{s.get("passed") or 0}</td>'
            f'<td class="failed">{s.get("failed") or 0}</td>'
            f'<td>{s.get("host") or "-"}</td></tr>'
        )
    return ('<table><thead><tr><th>session</th><th>started</th><th>passed</th>'
            '<th>failed</th><th>host</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def _render_session_detail(session: dict[str, Any],
                           tests: list[dict[str, Any]]) -> str:
    meta_rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in session.items())
    test_rows = "".join(
        f"<tr><td>{t.get('testcase_id') or '-'}</td>"
        f"<td>{t.get('test_node_id')}</td>"
        f"<td>{t.get('verdict') or '-'}</td>"
        f"<td>{t.get('duration_s') or '-'}</td></tr>"
        for t in tests
    )
    return (
        '<table><thead><tr><th>field</th><th>value</th></tr></thead>'
        f'<tbody>{meta_rows}</tbody></table>'
        '<h2>Tests</h2>'
        '<table><thead><tr><th>testcase</th><th>node</th><th>verdict</th>'
        '<th>duration</th></tr></thead>'
        f'<tbody>{test_rows}</tbody></table>'
    )


def _render_reservations(rows: list[ReservationInfo]) -> str:
    if not rows:
        return '<p class="empty">no active reservations</p>'
    body = "".join(
        f'<tr><td><code>{r.resource}</code></td>'
        f'<td>{r.acquired_by}</td>'
        f'<td>{r.expires_at.isoformat()}</td>'
        f'<td class="{"expired" if r.is_expired else ""}">'
        f'{"expired" if r.is_expired else "active"}</td>'
        f'<td>{r.reason or "-"}</td></tr>'
        for r in rows
    )
    return ('<table><thead><tr><th>resource</th><th>by</th><th>expires</th>'
            '<th>state</th><th>reason</th></tr></thead>'
            f'<tbody>{body}</tbody></table>')


def _render_trend_form(test: str | None, metric: str | None) -> str:
    return f"""<form method="get" action="/trends">
<label>Test ID <input name="test" value="{test or ''}" required></label>
<label>Metric <input name="metric" value="{metric or ''}" required></label>
<button type="submit">Plot trend</button>
</form>"""


def _render_trend_chart(test: str, metric: str,
                        points: list[tuple[Any, float]]) -> str:
    if not points:
        return f'<p class="empty">no data for test={test}, metric={metric}</p>'
    # Inline SVG chart — same pattern as the V2 HTML report sparklines.
    if len(points) == 1:
        return f'<p>1 data point: {points[0][1]}</p>'
    ys = [v for _, v in points]
    vmin, vmax = min(ys), max(ys)
    if vmin == vmax:
        return '<p class="empty">all values identical</p>'
    width, height = 600, 200
    coords = []
    for i, v in enumerate(ys):
        x = i * (width - 20) / max(1, len(ys) - 1) + 10
        y = height - 10 - (v - vmin) / (vmax - vmin) * (height - 20)
        coords.append(f"{x:.1f},{y:.1f}")
    points_str = " ".join(coords)
    rows = "".join(
        f"<tr><td>{ts.isoformat()}</td><td>{v}</td></tr>"
        for ts, v in points
    )
    return (
        f'<svg width="{width}" height="{height}" '
        f'style="border:1px solid #e0e0e0;background:#fafafa;">'
        f'<polyline fill="none" stroke="#1976d2" stroke-width="2" '
        f'points="{points_str}"/></svg>'
        '<table><thead><tr><th>when</th><th>value</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
    )


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    """Convert datetime values to ISO strings for JSON."""
    from datetime import datetime
    return {k: v.isoformat() if isinstance(v, datetime) else v
            for k, v in row.items()}
