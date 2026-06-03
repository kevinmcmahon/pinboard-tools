from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pinboard_tools.database.models import Database
from pinboard_tools.local_mirror import (
    _count_actionable_local_bookmarks,
    _fetch_local_bookmarks_by_hash,
    _fetch_pending_local_bookmarks,
    _mark_bookmark_pending_local,
    _mark_bookmarks_error,
    _mark_bookmarks_synced,
    _retry_error_bookmarks,
    _touch_synced_bookmarks,
)


def make_db(tmp_path: Path) -> Database:
    db = Database(str(tmp_path / "bookmarks.db"))
    db.init_schema()
    return db


def insert_bookmark(
    db: Database,
    *,
    hash_value: str,
    href: str,
    sync_status: str,
    last_synced_at: str | None = None,
) -> int:
    db.execute(
        """
        INSERT INTO bookmarks (
            hash, href, description, time, sync_status, last_synced_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            hash_value,
            href,
            f"Bookmark {hash_value}",
            "2026-06-02T12:00:00Z",
            sync_status,
            last_synced_at,
        ),
    )
    db.commit()
    row = db.execute(
        "SELECT id FROM bookmarks WHERE hash = ?", (hash_value,)
    ).fetchone()
    assert row is not None
    return int(row["id"])


def test_local_mirror_queries_sync_candidate_bookmarks(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    pending_id = insert_bookmark(
        db,
        hash_value="hash-pending",
        href="https://example.com/pending",
        sync_status="pending_local",
    )
    synced_id = insert_bookmark(
        db,
        hash_value="hash-synced",
        href="https://example.com/synced",
        sync_status="synced",
    )
    insert_bookmark(
        db,
        hash_value="hash-error",
        href="https://example.com/error",
        sync_status="error",
    )
    insert_bookmark(
        db,
        hash_value="hash-conflict",
        href="https://example.com/conflict",
        sync_status="conflict",
    )

    assert _count_actionable_local_bookmarks(db) == 2
    assert [bookmark["id"] for bookmark in _fetch_pending_local_bookmarks(db)] == [
        pending_id
    ]
    bookmarks_by_hash = _fetch_local_bookmarks_by_hash(db)
    assert list(bookmarks_by_hash) == [
        "hash-pending",
        "hash-synced",
        "hash-error",
        "hash-conflict",
    ]
    assert bookmarks_by_hash["hash-pending"]["id"] == pending_id
    assert bookmarks_by_hash["hash-synced"]["id"] == synced_id


def test_local_mirror_updates_sync_status_without_committing(
    tmp_path: Path,
) -> None:
    db = make_db(tmp_path)
    synced_id = insert_bookmark(
        db,
        hash_value="hash-synced",
        href="https://example.com/synced",
        sync_status="pending_local",
    )
    error_id = insert_bookmark(
        db,
        hash_value="hash-error",
        href="https://example.com/error",
        sync_status="pending_local",
    )
    pending_id = insert_bookmark(
        db,
        hash_value="hash-pending",
        href="https://example.com/pending",
        sync_status="synced",
    )

    now = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)
    _mark_bookmarks_synced(db, [synced_id], now)
    _mark_bookmarks_error(
        db,
        [{"id": synced_id}, {"id": error_id}],
        exclude_ids=[synced_id],
    )
    _mark_bookmark_pending_local(db, pending_id)

    rows = {
        row["id"]: row
        for row in db.execute(
            "SELECT id, sync_status, last_synced_at FROM bookmarks"
        ).fetchall()
    }
    assert rows[synced_id]["sync_status"] == "synced"
    assert rows[synced_id]["last_synced_at"] == now.isoformat()
    assert rows[error_id]["sync_status"] == "error"
    assert rows[pending_id]["sync_status"] == "pending_local"

    db.rollback()

    rolled_back_rows = {
        row["id"]: row
        for row in db.execute(
            "SELECT id, sync_status, last_synced_at FROM bookmarks"
        ).fetchall()
    }
    assert rolled_back_rows[synced_id]["sync_status"] == "pending_local"
    assert rolled_back_rows[error_id]["sync_status"] == "pending_local"
    assert rolled_back_rows[pending_id]["sync_status"] == "synced"


def test_retry_error_bookmarks_commits_reset(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    error_id = insert_bookmark(
        db,
        hash_value="hash-error",
        href="https://example.com/error",
        sync_status="error",
    )
    synced_id = insert_bookmark(
        db,
        hash_value="hash-synced",
        href="https://example.com/synced",
        sync_status="synced",
    )

    assert _retry_error_bookmarks(db) == 1
    db.rollback()

    rows = {
        row["id"]: row["sync_status"]
        for row in db.execute("SELECT id, sync_status FROM bookmarks").fetchall()
    }
    assert rows[error_id] == "pending_local"
    assert rows[synced_id] == "synced"


def test_touch_synced_bookmarks_updates_only_synced_rows(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    synced_id = insert_bookmark(
        db,
        hash_value="hash-synced",
        href="https://example.com/synced",
        sync_status="synced",
        last_synced_at="2026-06-02T12:00:00+00:00",
    )
    pending_id = insert_bookmark(
        db,
        hash_value="hash-pending",
        href="https://example.com/pending",
        sync_status="pending_local",
    )

    now = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)
    _touch_synced_bookmarks(db, now)

    rows = {
        row["id"]: row["last_synced_at"]
        for row in db.execute("SELECT id, last_synced_at FROM bookmarks").fetchall()
    }
    assert rows[synced_id] == now.isoformat()
    assert rows[pending_id] is None
