"""Per-test results publisher and session-level aggregation."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ResultsPublisher:
    """Collects records emitted during one test. Lives for one test's lifetime."""

    def __init__(self, test_node_id: str, testcase_id: str | None) -> None:
        self.test_node_id = test_node_id
        self.testcase_id = testcase_id
        self._records: list[dict[str, Any]] = []

    def publish(self, **kwargs: Any) -> None:
        """Append one record. Tests typically call this once per parametrized iteration."""
        self._records.append({
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **kwargs,
        })

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_id": self.test_node_id,
            "testcase_id": self.testcase_id,
            "records": list(self._records),
        }


def write_session_report(path: Path,
                         publishers: list[ResultsPublisher],
                         session_summary: dict[str, Any]) -> None:
    """Aggregate all per-test publishers into a single session report JSON file."""
    payload = {
        "session": session_summary,
        "tests": [p.to_dict() for p in publishers],
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
