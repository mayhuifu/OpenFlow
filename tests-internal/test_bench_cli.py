"""Tests for the V5a ``openflow bench`` CLI."""
from pathlib import Path

from openflow.bench.cli import cli_main


def test_reserve_subcommand(tmp_path: Path, capsys):
    store = tmp_path / "reservations.json"
    rc = cli_main([
        "--store", str(store),
        "reserve", "--resource", "TCPIP::1::INSTR",
        "--for", "1h", "--by", "alice", "--reason", "test",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "reserved" in out
    assert "alice" in out


def test_reserve_then_release(tmp_path: Path, capsys):
    store = tmp_path / "reservations.json"
    cli_main(["--store", str(store), "reserve", "--resource", "R1",
              "--for", "1h", "--by", "alice"])
    capsys.readouterr()
    rc = cli_main(["--store", str(store), "release", "--resource", "R1"])
    assert rc == 0
    assert "released R1" in capsys.readouterr().out


def test_reserve_conflict_returns_1(tmp_path: Path, capsys):
    store = tmp_path / "reservations.json"
    cli_main(["--store", str(store), "reserve", "--resource", "R1",
              "--for", "1h", "--by", "alice"])
    capsys.readouterr()
    rc = cli_main(["--store", str(store), "reserve", "--resource", "R1",
                   "--for", "1h", "--by", "bob"])
    assert rc == 1
    assert "conflict" in capsys.readouterr().err


def test_status_shows_active_reservations(tmp_path: Path, capsys):
    store = tmp_path / "reservations.json"
    cli_main(["--store", str(store), "reserve", "--resource", "R1",
              "--for", "1h", "--by", "alice"])
    cli_main(["--store", str(store), "reserve", "--resource", "R2",
              "--for", "1h", "--by", "bob"])
    capsys.readouterr()
    rc = cli_main(["--store", str(store), "status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "R1" in out
    assert "R2" in out
    assert "alice" in out
    assert "bob" in out


def test_status_empty(tmp_path: Path, capsys):
    store = tmp_path / "reservations.json"
    rc = cli_main(["--store", str(store), "status"])
    assert rc == 0
    assert "no reservations" in capsys.readouterr().out


def test_openflow_cli_dispatches_bench(tmp_path: Path, capsys):
    """`openflow bench status` dispatches through the top-level entry."""
    from openflow.migrate.cli import main as openflow_main
    store = tmp_path / "reservations.json"
    rc = openflow_main(["bench", "--store", str(store), "status"])
    assert rc == 0
    assert "no reservations" in capsys.readouterr().out
