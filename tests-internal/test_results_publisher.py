import json
from pathlib import Path

from openflow.results import ResultsPublisher, write_session_report


def test_publisher_records_kwargs_in_order():
    pub = ResultsPublisher(test_node_id="tests/test_x.py::test_y[1]", testcase_id="U300B0-X-001")
    pub.publish(gain=10, delta=0.1)
    pub.publish(gain=20, delta=0.2)

    d = pub.to_dict()
    assert d["test_id"] == "tests/test_x.py::test_y[1]"
    assert d["testcase_id"] == "U300B0-X-001"
    assert len(d["records"]) == 2
    assert d["records"][0]["gain"] == 10
    assert d["records"][1]["gain"] == 20


def test_publisher_each_record_has_timestamp():
    pub = ResultsPublisher(test_node_id="x", testcase_id=None)
    pub.publish(a=1)
    rec = pub.to_dict()["records"][0]
    assert "timestamp" in rec
    assert rec["timestamp"].endswith("Z")


def test_write_session_report_writes_json(tmp_path: Path):
    pub_a = ResultsPublisher(test_node_id="test_a", testcase_id="ID-A")
    pub_a.publish(value=1)
    pub_b = ResultsPublisher(test_node_id="test_b", testcase_id="ID-B")
    pub_b.publish(value=2)
    pub_b.publish(value=3)

    out = tmp_path / "report.json"
    write_session_report(out, publishers=[pub_a, pub_b],
                         session_summary={"exit_status": 0})

    payload = json.loads(out.read_text())
    assert payload["session"]["exit_status"] == 0
    assert len(payload["tests"]) == 2
    assert payload["tests"][0]["test_id"] == "test_a"
    assert payload["tests"][1]["records"][1]["value"] == 3
