from __future__ import annotations

from pathlib import Path

import pytest

from pinboard_tools import InvalidPinboardPostError, upsert_pinboard_post
from pinboard_tools.database.models import Database, get_bookmark_tags


def remote_post(**overrides: object) -> dict[str, object]:
    post: dict[str, object] = {
        "href": "https://example.com/article",
        "description": "Example Article",
        "extended": "A useful article.",
        "meta": "abc123",
        "hash": "hash-example",
        "time": "2026-06-02T12:00:00Z",
        "shared": "yes",
        "toread": "no",
        "tags": "python testing",
    }
    post.update(overrides)
    return post


def test_upsert_pinboard_post_inserts_bookmark_and_tags(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "bookmarks.db"))
    db.init_schema()

    bookmark = upsert_pinboard_post(db, remote_post())

    row = db.execute(
        "SELECT * FROM bookmarks WHERE href = ?", ("https://example.com/article",)
    ).fetchone()
    assert row is not None
    assert bookmark.id == row["id"]
    assert row["description"] == "Example Article"
    assert row["extended"] == "A useful article."
    assert row["hash"] == "hash-example"
    assert row["shared"] == 1
    assert row["toread"] == 0
    assert row["sync_status"] == "synced"
    assert row["last_synced_at"] is not None
    assert get_bookmark_tags(db, row["id"]) == ["python", "testing"]


def test_upsert_pinboard_post_updates_existing_bookmark_and_tags(
    tmp_path: Path,
) -> None:
    db = Database(str(tmp_path / "bookmarks.db"))
    db.init_schema()
    upsert_pinboard_post(db, remote_post())

    bookmark = upsert_pinboard_post(
        db,
        remote_post(
            description="Updated Title",
            extended="Updated description.",
            shared="no",
            toread="yes",
            tags="updated local-copy",
        ),
    )

    rows = db.execute(
        "SELECT * FROM bookmarks WHERE href = ?", ("https://example.com/article",)
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert bookmark.id == row["id"]
    assert row["description"] == "Updated Title"
    assert row["extended"] == "Updated description."
    assert row["shared"] == 0
    assert row["toread"] == 1
    assert row["sync_status"] == "synced"
    assert get_bookmark_tags(db, row["id"]) == ["local-copy", "updated"]


def test_upsert_pinboard_post_updates_existing_bookmark_when_href_changes(
    tmp_path: Path,
) -> None:
    db = Database(str(tmp_path / "bookmarks.db"))
    db.init_schema()
    original = upsert_pinboard_post(db, remote_post())

    bookmark = upsert_pinboard_post(
        db,
        remote_post(
            href="https://example.com/moved-article",
            description="Moved Article",
            tags="moved remote",
        ),
    )

    rows = db.execute("SELECT * FROM bookmarks").fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert bookmark.id == original.id == row["id"]
    assert row["href"] == "https://example.com/moved-article"
    assert row["description"] == "Moved Article"
    assert row["hash"] == "hash-example"
    assert row["sync_status"] == "synced"
    assert get_bookmark_tags(db, row["id"]) == ["moved", "remote"]


def test_upsert_pinboard_post_updates_existing_bookmark_when_hash_changes(
    tmp_path: Path,
) -> None:
    db = Database(str(tmp_path / "bookmarks.db"))
    db.init_schema()
    original = upsert_pinboard_post(db, remote_post())

    bookmark = upsert_pinboard_post(
        db,
        remote_post(
            hash="hash-updated",
            description="Updated Hash Article",
            tags="hash remote",
        ),
    )

    rows = db.execute(
        "SELECT * FROM bookmarks WHERE href = ?", ("https://example.com/article",)
    ).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert bookmark.id == original.id == row["id"]
    assert row["href"] == "https://example.com/article"
    assert row["description"] == "Updated Hash Article"
    assert row["hash"] == "hash-updated"
    assert row["sync_status"] == "synced"
    assert get_bookmark_tags(db, row["id"]) == ["hash", "remote"]


def test_upsert_pinboard_post_rejects_missing_required_fields(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "bookmarks.db"))
    db.init_schema()

    with pytest.raises(InvalidPinboardPostError, match="hash"):
        upsert_pinboard_post(db, remote_post(hash=""))
