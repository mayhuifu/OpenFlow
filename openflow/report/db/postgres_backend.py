"""PostgreSQL backend for V4 persistent results.

Optional — requires the ``postgres`` extra (``uv sync --extra postgres``).
The local SQLite backend stays the source of truth; PostgreSQL is for
multi-bench shared queries + dashboards.

Same interface as ``SQLiteBackend``:

    backend = PostgreSQLBackend("postgresql://user:pass@host/dbname")
    backend.ensure_schema()
    backend.write_session(...)
    sessions = backend.list_sessions()

The schema is identical (SQLAlchemy Core abstracts dialect differences
for the table definitions we use). Indexes are auto-created via
``metadata.create_all``.

Failure mode: callers (the pytest plugin) treat PostgreSQL writes as
best-effort. If the connection fails the test session still succeeds —
only a warning is logged. Local SQLite is the authoritative store.
"""
from __future__ import annotations

# We inherit everything from the SQLite backend except the engine URL
# construction — SQLAlchemy Core hides the dialect differences for our
# narrow set of operations.
from openflow.report.db.sqlite_backend import SQLiteBackend


class PostgreSQLBackend(SQLiteBackend):
    """PostgreSQL persistence backend (optional, multi-bench shared)."""

    def __init__(self, dsn: str) -> None:
        # Bypass SQLiteBackend.__init__ to construct a PostgreSQL engine.
        from sqlalchemy import create_engine

        self.path = dsn  # str, not Path — for symmetry with parent
        self._engine = create_engine(dsn)
