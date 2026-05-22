"""V5c: read-only web dashboard.

FastAPI + Jinja2 templating (no JS framework, no SPA build). Reads
exclusively from the V4 SQLite database and the V5a reservation store.
**No write endpoints** — edits happen by re-running tests with corrected
config, not by clicking buttons.

Entry point:

    uv run openflow dashboard serve --db /path/to/report.db [--host 0.0.0.0] [--port 8080]

…or use the FastAPI app directly:

    from openflow.dashboard.server import create_app
    app = create_app(db_path="/path/to/report.db")
"""
from openflow.dashboard.server import create_app

__all__ = ["create_app"]
