"""SQLite backend for V4 persistent results.

Default storage backend — zero-config, on-disk file. Suitable for
single-bench labs. Use ``PostgreSQLBackend`` (optional ``postgres``
extra) for multi-bench shared databases.

Usage:

    backend = SQLiteBackend(Path("report.db"))
    backend.ensure_schema()
    backend.ingest_json(Path("report.json"))
    sessions = backend.list_sessions()
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, desc, insert, select
from sqlalchemy.engine import Engine

from openflow.report.db.schema import (
    cases,
    measurements,
    metadata,
    schema_version,
    sessions,
    tests,
)

logger = logging.getLogger(__name__)


class SQLiteBackend:
    """SQLite persistence backend.

    Parameters
    ----------
    path : Path | str
        Path to the SQLite database file. Use ``":memory:"`` for an
        in-memory database (test-only).
    """

    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path) if path != ":memory:" else ":memory:"
        url = (f"sqlite:///{self.path}" if self.path != ":memory:"
               else "sqlite:///:memory:")
        # check_same_thread=False so pytest fixtures (which can share an
        # engine across thread-pool workers) don't trip up.
        self._engine: Engine = create_engine(
            url, connect_args={"check_same_thread": False})

    # --- schema management ------------------------------------------------
    def ensure_schema(self) -> None:
        """Create tables + record the current schema version. Idempotent."""
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(schema_version.c.version)
                .order_by(desc(schema_version.c.version))
                .limit(1)
            ).scalar()
            if existing is None:
                conn.execute(insert(schema_version).values(
                    version=self.SCHEMA_VERSION,
                    applied_at=datetime.utcnow(),
                ))

    def current_schema_version(self) -> int | None:
        """Return the highest applied schema version, or None if none."""
        with self._engine.begin() as conn:
            return conn.execute(
                select(schema_version.c.version)
                .order_by(desc(schema_version.c.version))
                .limit(1)
            ).scalar()

    # --- session writes ---------------------------------------------------
    def write_session(self, *, session_id: str, started_at: datetime,
                      finished_at: datetime | None = None,
                      host: str | None = None,
                      openflow_version: str | None = None,
                      config_path: str | None = None,
                      passed: int | None = None,
                      failed: int | None = None,
                      exit_status: int | None = None) -> None:
        """Insert a session row. Caller is responsible for uniqueness."""
        with self._engine.begin() as conn:
            conn.execute(insert(sessions).values(
                session_id=session_id,
                started_at=started_at,
                finished_at=finished_at,
                host=host,
                openflow_version=openflow_version,
                config_path=config_path,
                passed=passed,
                failed=failed,
                exit_status=exit_status,
            ))

    def write_test(self, *, session_id: str, test_node_id: str,
                   testcase_id: str | None = None,
                   verdict: str | None = None,
                   duration_s: float | None = None) -> int:
        """Insert a test row. Returns the auto-assigned ``test_id``."""
        with self._engine.begin() as conn:
            result = conn.execute(insert(tests).values(
                session_id=session_id,
                test_node_id=test_node_id,
                testcase_id=testcase_id,
                verdict=verdict,
                duration_s=duration_s,
            ))
            assert result.inserted_primary_key is not None
            return int(result.inserted_primary_key[0])

    def write_case(self, *, test_id: int,
                   params: dict[str, Any] | None = None,
                   recorded_at: datetime | None = None) -> int:
        """Insert a case row. Returns the auto-assigned ``case_id``."""
        with self._engine.begin() as conn:
            result = conn.execute(insert(cases).values(
                test_id=test_id,
                params=params,
                recorded_at=recorded_at,
            ))
            assert result.inserted_primary_key is not None
            return int(result.inserted_primary_key[0])

    def write_measurement(self, *, case_id: int, name: str,
                          value: float | None = None,
                          text_value: str | None = None,
                          unit: str | None = None) -> None:
        """Insert one measurement row."""
        with self._engine.begin() as conn:
            conn.execute(insert(measurements).values(
                case_id=case_id,
                name=name,
                value=value,
                text_value=text_value,
                unit=unit,
            ))

    # --- query surface ----------------------------------------------------
    def list_sessions(self) -> list[dict[str, Any]]:
        """Return all sessions, most recent first."""
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(sessions).order_by(desc(sessions.c.started_at))
            ).mappings().all()
            return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(sessions).where(sessions.c.session_id == session_id)
            ).mappings().first()
            return dict(row) if row else None

    def query_tests(self, *, where: str | None = None,
                    since_seconds: int | None = None,
                    ) -> list[dict[str, Any]]:
        """Return tests joined with their session metadata.

        ``where`` is a raw SQL fragment (e.g. ``"testcase_id LIKE '%TX_EVM%'"``).
        ``since_seconds`` is a time filter against ``sessions.started_at``.
        """
        from sqlalchemy import text
        # Join tests with sessions so the engineer can filter by both.
        stmt = (
            select(
                tests.c.test_id,
                tests.c.session_id,
                tests.c.test_node_id,
                tests.c.testcase_id,
                tests.c.verdict,
                tests.c.duration_s,
                sessions.c.started_at,
                sessions.c.host,
            )
            .join_from(tests, sessions, tests.c.session_id == sessions.c.session_id)
        )
        if where:
            stmt = stmt.where(text(where))
        if since_seconds is not None:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(seconds=since_seconds)
            stmt = stmt.where(sessions.c.started_at >= cutoff)
        stmt = stmt.order_by(desc(sessions.c.started_at), tests.c.test_id)
        with self._engine.begin() as conn:
            return [dict(r) for r in conn.execute(stmt).mappings().all()]

    def trend(self, *, testcase_id: str, metric: str,
              since_seconds: int | None = None,
              ) -> list[tuple[datetime, float]]:
        """Return ``(started_at, value)`` rows for a metric across sessions.

        Filters measurements where ``name == metric`` and the parent test
        has ``testcase_id == <testcase_id>``. Sorted oldest-first so
        callers can plot directly.
        """
        stmt = (
            select(sessions.c.started_at, measurements.c.value)
            .join_from(measurements, cases, measurements.c.case_id == cases.c.case_id)
            .join_from(cases, tests, cases.c.test_id == tests.c.test_id)
            .join_from(tests, sessions, tests.c.session_id == sessions.c.session_id)
            .where(measurements.c.name == metric)
            .where(tests.c.testcase_id == testcase_id)
            .where(measurements.c.value.isnot(None))
        )
        if since_seconds is not None:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(seconds=since_seconds)
            stmt = stmt.where(sessions.c.started_at >= cutoff)
        stmt = stmt.order_by(sessions.c.started_at)
        with self._engine.begin() as conn:
            return [(r[0], float(r[1])) for r in conn.execute(stmt).all()]

    # --- JSON ingest ------------------------------------------------------
    def ingest_json(self, json_path: Path | str) -> str:
        """Load a V1-V3 ``report.json`` into the database.

        Returns the synthesized ``session_id``. If the JSON's session
        block has its own session_id, that's used; otherwise we
        derive one from the file's hash + mtime so reingests are stable.
        """
        json_path = Path(json_path)
        data = json.loads(json_path.read_text())
        session_block = data.get("session", {})

        # Derive a stable session_id if absent.
        if "session_id" in session_block:
            session_id = str(session_block["session_id"])
        else:
            session_id = self._derive_session_id(json_path)

        # Derive timestamps. Older reports may not have started_at; fall
        # back to file mtime so we have something monotonic.
        started_at = self._parse_dt(session_block.get("started_at"))
        if started_at is None:
            started_at = datetime.utcfromtimestamp(json_path.stat().st_mtime)
        finished_at = self._parse_dt(session_block.get("finished_at"))

        self.write_session(
            session_id=session_id,
            started_at=started_at,
            finished_at=finished_at,
            host=session_block.get("host"),
            openflow_version=session_block.get("openflow_version"),
            config_path=session_block.get("config_path"),
            passed=session_block.get("passed"),
            failed=session_block.get("failed"),
            exit_status=session_block.get("exit_status"),
        )

        for test_block in data.get("tests", []):
            try:
                test_id = self.write_test(
                    session_id=session_id,
                    test_node_id=str(test_block.get("test_id", "<unknown>")),
                    testcase_id=test_block.get("testcase_id"),
                )
            except Exception as exc:
                logger.warning("ingest: skipping malformed test row: %s", exc)
                continue

            for record in test_block.get("records", []):
                recorded_at = self._parse_dt(record.get("timestamp"))
                # Build params from non-numeric scalars (and timestamp goes
                # in the case row, not measurements).
                params: dict[str, Any] = {}
                numeric: list[tuple[str, float]] = []
                text_vals: list[tuple[str, str]] = []
                for k, v in record.items():
                    if k == "timestamp":
                        continue
                    if isinstance(v, bool):
                        # bools serialize cleanly through JSON params column
                        params[k] = v
                    elif isinstance(v, (int, float)):
                        numeric.append((k, float(v)))
                    elif isinstance(v, str):
                        text_vals.append((k, v))
                    elif v is None:
                        text_vals.append((k, ""))
                    else:
                        # Lists / dicts go in params (case-level metadata).
                        params[k] = v

                case_id = self.write_case(
                    test_id=test_id,
                    params=params if params else None,
                    recorded_at=recorded_at,
                )
                for name, value in numeric:
                    self.write_measurement(
                        case_id=case_id, name=name, value=value)
                for name, text in text_vals:
                    self.write_measurement(
                        case_id=case_id, name=name, text_value=text)

        return session_id

    # --- internals --------------------------------------------------------
    @staticmethod
    def _derive_session_id(path: Path) -> str:
        """Stable session_id from filename + content hash."""
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        return f"{path.stem}-{content_hash}"

    @staticmethod
    def _parse_dt(value: Any) -> datetime | None:
        """Parse an ISO-8601 timestamp; tolerate the 'Z' suffix that V1
        timestamps use."""
        if not value or not isinstance(value, str):
            return None
        # Python 3.11 fromisoformat handles 'Z' since 3.11.
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
