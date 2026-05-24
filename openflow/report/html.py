"""HTML report renderer for OpenFlow session JSON.

Single-file, no external CDN, no JS framework. Uses hand-rolled SVG
sparklines for numeric measurement trends (no Chart.js dependency).

Designed for the V2 use case: an engineer emails the bench report to a
colleague, who opens it in a browser. Self-contained means a clicked
file works regardless of network state.

Layout:

  +--------------------------------------------------------------+
  | Header: openflow version, started_at, host, config path      |
  +--------------------------------------------------------------+
  | Summary band: passed | failed | skipped | duration           |
  +--------------------------------------------------------------+
  | Per-test row: test_id | testcase_id | verdict | duration     |
  |   Expandable details: per-record key=value table + sparkline |
  |   for any numeric series across records                      |
  +--------------------------------------------------------------+

Input: the JSON written by openflow.results.write_session_report:

  {
    "session": {"exit_status": 0, "passed": 5, "failed": 0, ...},
    "tests": [
      {"test_id": "tests/test_x.py::test_foo[0]",
       "testcase_id": "TC1",
       "records": [{"timestamp": "...", "value": 1.0}, ...]},
      ...
    ]
  }

Output: a single .html file with all CSS + JS inlined.
"""
from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

# Embedded CSS — minimal, dark-friendly, readable on print.
_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       margin: 2rem auto; max-width: 1100px; color: #1a1a1a; padding: 0 1rem; }
h1 { margin: 0 0 0.5rem 0; font-size: 1.5rem; }
.header-meta { color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }
.header-meta span { margin-right: 1rem; }
.summary { display: flex; gap: 1rem; margin: 1.5rem 0; }
.summary-card { flex: 1; padding: 1rem; border-radius: 6px;
                background: #f5f5f5; text-align: center; }
.summary-card .value { font-size: 1.8rem; font-weight: 600; display: block; }
.summary-card .label { font-size: 0.85rem; color: #666; }
.summary-card.passed { background: #e6f5e6; color: #2e7d32; }
.summary-card.failed { background: #fde7e7; color: #c62828; }
table { width: 100%; border-collapse: collapse; margin: 1.5rem 0; }
th, td { text-align: left; padding: 0.5rem 0.75rem;
         border-bottom: 1px solid #e0e0e0; }
th { background: #fafafa; font-weight: 600; font-size: 0.85rem;
     text-transform: uppercase; color: #666; }
.verdict-pass { color: #2e7d32; font-weight: 600; }
.verdict-fail { color: #c62828; font-weight: 600; }
.verdict-skip { color: #999; font-weight: 600; }
details { margin: 0.25rem 0; }
details summary { cursor: pointer; padding: 0.25rem 0;
                  list-style: none; font-family: monospace; font-size: 0.9rem; }
details summary::-webkit-details-marker { display: none; }
details summary::before { content: '▶ '; }
details[open] summary::before { content: '▼ '; }
.records-table { font-size: 0.85rem; margin-left: 1.5rem; max-width: 100%; }
.records-table th { background: transparent; border: none; }
.sparkline { vertical-align: middle; margin-left: 0.5rem; }
.test-row.failed td { background: #fff5f5; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #e0e0e0;
         color: #999; font-size: 0.8rem; text-align: center; }
""".strip()


class HTMLReportRenderer:
    """Render an OpenFlow session JSON file into a single self-contained HTML."""

    def __init__(self, json_path: Path | str) -> None:
        self.json_path = Path(json_path)
        self.data: dict[str, Any] = json.loads(self.json_path.read_text())

    def render(self, output_path: Path | str) -> None:
        """Render to the given output path. Overwrites if it exists.

        Auto-creates the parent directory if it doesn't exist — same
        ergonomic fix as :func:`openflow.results.write_session_report`.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        html_str = self._render_str()
        out.write_text(html_str, encoding="utf-8")

    def render_str(self) -> str:
        """Alias for ``_render_str`` exposed for tests / programmatic use."""
        return self._render_str()

    # --- internals --------------------------------------------------------
    def _render_str(self) -> str:
        session = self.data.get("session", {})
        tests = self.data.get("tests", [])

        passed = session.get("passed", 0)
        failed = session.get("failed", 0)
        exit_status = session.get("exit_status", 0)
        total = passed + failed

        # Optional header metadata fields — some session_summary dicts include
        # these (started_at, host, config_path); we render whatever is there.
        meta_lines = []
        for key in ("started_at", "finished_at", "host", "config_path",
                    "openflow_version"):
            if key in session:
                meta_lines.append(
                    f'<span><strong>{html.escape(key)}:</strong> '
                    f'{html.escape(str(session[key]))}</span>')

        rows = []
        for test in tests:
            rows.append(self._render_test_row(test))

        body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>OpenFlow report — {html.escape(str(self.json_path.name))}</title>
<style>
{_CSS}
</style>
</head>
<body>
<h1>OpenFlow report</h1>
<div class="header-meta">
  <span><strong>source:</strong> {html.escape(str(self.json_path))}</span>
  {''.join(meta_lines)}
</div>

<div class="summary">
  <div class="summary-card passed">
    <span class="value">{passed}</span>
    <span class="label">passed</span>
  </div>
  <div class="summary-card failed">
    <span class="value">{failed}</span>
    <span class="label">failed</span>
  </div>
  <div class="summary-card">
    <span class="value">{total}</span>
    <span class="label">total</span>
  </div>
  <div class="summary-card">
    <span class="value">{exit_status}</span>
    <span class="label">exit status</span>
  </div>
</div>

<table>
<thead>
  <tr>
    <th>Test</th>
    <th>Testcase ID</th>
    <th>Records</th>
    <th>Detail</th>
  </tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>

<footer>OpenFlow — single-file HTML report. No external assets loaded.</footer>
</body>
</html>
"""
        return body

    def _render_test_row(self, test: dict[str, Any]) -> str:
        test_id = test.get("test_id", "<unknown>")
        testcase_id = test.get("testcase_id") or "—"
        records = test.get("records", [])

        # Build the expandable detail with key/value table + sparklines.
        records_table = self._render_records_table(records)

        detail = (
            f'<details><summary>show {len(records)} record(s)</summary>'
            f'{records_table}</details>'
        ) if records else "—"

        return f"""<tr class="test-row">
  <td><code>{html.escape(test_id)}</code></td>
  <td><code>{html.escape(str(testcase_id))}</code></td>
  <td>{len(records)}</td>
  <td>{detail}</td>
</tr>
"""

    def _render_records_table(self, records: list[dict[str, Any]]) -> str:
        if not records:
            return "<em>no records</em>"

        # Collect all keys across records (excluding 'timestamp') so each
        # record renders as a row.
        all_keys: list[str] = []
        seen: set[str] = set()
        for rec in records:
            for k in rec:
                if k == "timestamp":
                    continue
                if k not in seen:
                    seen.add(k)
                    all_keys.append(k)

        # Build header row + sparklines for numeric series.
        header_cells = ['<th>timestamp</th>']
        for k in all_keys:
            sparkline = self._maybe_sparkline_for_key(records, k)
            header_cells.append(f'<th>{html.escape(k)}{sparkline}</th>')

        body_rows = []
        for rec in records:
            cells = [f'<td>{html.escape(str(rec.get("timestamp", "")))}</td>']
            for k in all_keys:
                v = rec.get(k, "")
                cells.append(f'<td>{html.escape(str(v))}</td>')
            body_rows.append(f'<tr>{"".join(cells)}</tr>')

        return f"""<table class="records-table">
<thead><tr>{''.join(header_cells)}</tr></thead>
<tbody>
{''.join(body_rows)}
</tbody>
</table>"""

    @staticmethod
    def _maybe_sparkline_for_key(records: list[dict[str, Any]], key: str) -> str:
        """If all values for `key` across records are numeric, render a tiny
        inline SVG sparkline next to the column header."""
        values: list[float] = []
        for rec in records:
            v = rec.get(key)
            if v is None:
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                return ""  # non-numeric — no sparkline
            if math.isnan(fv) or math.isinf(fv):
                continue
            values.append(fv)
        if len(values) < 2:
            return ""

        vmin = min(values)
        vmax = max(values)
        if vmin == vmax:
            return ""  # flat series — sparkline conveys nothing

        # 80 x 20 px viewbox; map values across (vmin, vmax) → (18, 2) y range.
        width = 80
        height = 20
        n = len(values)
        points = []
        for i, v in enumerate(values):
            x = i * (width - 2) / max(1, n - 1) + 1
            y = height - 2 - (v - vmin) / (vmax - vmin) * (height - 4)
            points.append(f"{x:.1f},{y:.1f}")
        polyline = " ".join(points)
        return (f'<svg class="sparkline" width="{width}" height="{height}" '
                f'viewBox="0 0 {width} {height}">'
                f'<polyline fill="none" stroke="#1976d2" stroke-width="1.2" '
                f'points="{polyline}"/></svg>')
