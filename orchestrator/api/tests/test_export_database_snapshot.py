import sqlite3
import sys
from pathlib import Path

import pytest

from app.scripts import export_database_snapshot
from app.scripts.export_database_snapshot import SnapshotExportError, create_snapshot, sqlite_path_from_url


def create_source_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE vacancies (id INTEGER PRIMARY KEY, title TEXT NOT NULL)")
        connection.execute("INSERT INTO vacancies (title) VALUES ('Original vacancy')")


def test_create_snapshot_uses_consistent_copy_and_keeps_source_unchanged(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "exports" / "snapshot.db"
    create_source_database(source)
    source_bytes_before = source.read_bytes()

    create_snapshot(source, output)

    assert source.read_bytes() == source_bytes_before
    with sqlite3.connect(output) as connection:
        assert connection.execute("SELECT title FROM vacancies").fetchone() == ("Original vacancy",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_create_snapshot_replaces_existing_output_only_after_success(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "snapshot.db"
    create_source_database(source)
    output.write_bytes(b"old snapshot")

    create_snapshot(source, output)

    with sqlite3.connect(output) as connection:
        assert connection.execute("SELECT COUNT(*) FROM vacancies").fetchone() == (1,)


def test_create_snapshot_rejects_missing_source_without_touching_existing_output(tmp_path: Path) -> None:
    output = tmp_path / "snapshot.db"
    output.write_bytes(b"known good snapshot")

    with pytest.raises(SnapshotExportError, match="does not exist"):
        create_snapshot(tmp_path / "missing.db", output)

    assert output.read_bytes() == b"known good snapshot"


def test_create_snapshot_rejects_source_as_output(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    create_source_database(source)

    with pytest.raises(SnapshotExportError, match="must differ"):
        create_snapshot(source, source)


def test_create_snapshot_reports_invalid_output_path(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    invalid_parent = tmp_path / "not-a-directory"
    create_source_database(source)
    invalid_parent.write_text("file")

    with pytest.raises(SnapshotExportError, match="sqlite backup failed"):
        create_snapshot(source, invalid_parent / "snapshot.db")


@pytest.mark.parametrize(
    ("database_url", "expected"),
    [
        ("sqlite:///./data/app.db", Path("data/app.db")),
        ("sqlite:////app/data/app.db", Path("/app/data/app.db")),
    ],
)
def test_sqlite_path_from_url(database_url: str, expected: Path) -> None:
    assert sqlite_path_from_url(database_url) == expected


def test_sqlite_path_from_url_rejects_non_file_sqlite_url() -> None:
    with pytest.raises(SnapshotExportError):
        sqlite_path_from_url("postgresql://example.invalid/db")


def test_cli_returns_nonzero_for_missing_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    missing_source = tmp_path / "missing.db"
    output = tmp_path / "snapshot.db"
    monkeypatch.setattr(sys, "argv", ["export_database_snapshot", "--source", str(missing_source), "--output", str(output)])

    assert export_database_snapshot.main() == 1
    assert "Database snapshot export failed" in capsys.readouterr().err
    assert not output.exists()
