"""V4: persistent results storage.

Default backend is SQLite — zero-config, file lives next to the test
report. Optional PostgreSQL backend (``uv sync --extra postgres``) for
shared multi-bench labs.

Public surface:

    SQLiteBackend(path: Path)
    PostgreSQLBackend(dsn: str)       # requires the `postgres` extra

Both expose the same interface: ``ensure_schema``, ``write_session``,
``write_test``, ``write_case``, ``write_measurement``, ``list_sessions``,
``get_session``, ``query_tests``, ``ingest_json``.
"""
from openflow.report.db.sqlite_backend import SQLiteBackend

__all__ = ["SQLiteBackend"]
