"""Create a consistent SQLite snapshot for offline inspection."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings


class SnapshotExportError(RuntimeError):
    """Raised when a snapshot cannot be created safely."""


def sqlite_path_from_url(database_url: str) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise SnapshotExportError("only sqlite database URLs are supported")
    raw_path = database_url.removeprefix(prefix)
    if not raw_path or raw_path == ":memory:":
        raise SnapshotExportError("database URL must identify a file")
    return Path(raw_path).expanduser()


def create_snapshot(source: Path, output: Path) -> None:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_file():
        raise SnapshotExportError(f"source database does not exist: {source}")
    if source == output:
        raise SnapshotExportError("output path must differ from source database")

    temporary_output = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    source_connection: sqlite3.Connection | None = None
    destination_connection: sqlite3.Connection | None = None
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
        destination_connection = sqlite3.connect(temporary_output)
        source_connection.backup(destination_connection)
        integrity = destination_connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise SnapshotExportError("snapshot integrity check failed")
        destination_connection.close()
        destination_connection = None
        source_connection.close()
        source_connection = None
        os.replace(temporary_output, output)
    except (OSError, sqlite3.Error) as exc:
        raise SnapshotExportError(f"sqlite backup failed: {exc}") from exc
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()
        temporary_output.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite snapshot through the SQLite backup API.")
    parser.add_argument("--output", required=True, type=Path, help="Snapshot destination path.")
    parser.add_argument("--source", type=Path, help="Source SQLite file. Defaults to DATABASE_URL.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        source = args.source or sqlite_path_from_url(get_settings().database_url)
        create_snapshot(source, args.output)
    except SnapshotExportError as exc:
        print(f"Database snapshot export failed: {exc}", file=sys.stderr)
        return 1
    print(f"Database snapshot created: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
