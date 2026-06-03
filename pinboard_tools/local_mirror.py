# ABOUTME: Public helpers for mirroring Pinboard posts into the local database
# ABOUTME: Supports write-through clients that save remotely and keep a local copy

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from .database.models import Bookmark, Database, bookmark_from_row, set_bookmark_tags
from .utils.datetime import parse_boolean


class InvalidPinboardPostError(ValueError):
    """Raised when a Pinboard post cannot be mirrored locally."""


def upsert_pinboard_post(db: Database, post: Mapping[str, Any]) -> Bookmark:
    """Insert or update a Pinboard-shaped post in the local database."""
    remote = _validate_post(post)
    tags = _parse_tags(remote.get("tags", ""))
    synced_at = datetime.now(UTC).isoformat()

    db.enter_sync_context()
    try:
        row = _fetch_existing_mirror_bookmark(db, remote)

        if row is None:
            _insert_synced_bookmark(db, remote, synced_at)
            row = _fetch_bookmark_identity_by_href(db, remote["href"])
            if row is None:
                raise InvalidPinboardPostError(
                    f"Mirrored bookmark could not be found: {remote['href']}"
                )
        else:
            bookmark_id = int(row["id"])
            _replace_synced_bookmark(
                db, bookmark_id, remote, synced_at, row["created_at"]
            )

        bookmark_id = int(row["id"])
        set_bookmark_tags(db, bookmark_id, tags)
        _clear_local_mirror_pending_state(db, bookmark_id, synced_at)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.exit_sync_context()

    mirrored = _fetch_mirrored_bookmark(db, bookmark_id)
    if mirrored is None:
        raise InvalidPinboardPostError(
            f"Mirrored bookmark could not be loaded: {remote['href']}"
        )
    return bookmark_from_row(dict(mirrored))


def _count_actionable_local_bookmarks(db: Database) -> int:
    cursor = db.execute(
        """
        SELECT COUNT(*) as count
        FROM bookmarks
        WHERE sync_status IN ('pending_local', 'pending_remote', 'conflict')
        """
    )
    return int(cursor.fetchone()["count"])


def _retry_error_bookmarks(db: Database) -> int:
    cursor = db.execute(
        "SELECT COUNT(*) as count FROM bookmarks WHERE sync_status = 'error'"
    )
    count = int(cursor.fetchone()["count"])

    if count > 0:
        db.execute(
            "UPDATE bookmarks SET sync_status = 'pending_local' WHERE sync_status = 'error'"
        )
        db.commit()

    return count


def _fetch_pending_local_bookmarks(db: Database) -> list[dict[str, Any]]:
    cursor = db.execute("SELECT * FROM bookmarks WHERE sync_status = 'pending_local'")
    return [dict(row) for row in cursor]


def _fetch_local_bookmarks_by_hash(db: Database) -> dict[str, dict[str, Any]]:
    cursor = db.execute("SELECT * FROM bookmarks")
    return {row["hash"]: dict(row) for row in cursor}


def _mark_bookmarks_synced(
    db: Database, bookmark_ids: list[int], synced_at: datetime | None = None
) -> None:
    if not bookmark_ids:
        return
    now_iso = (synced_at or datetime.now(UTC)).isoformat()
    for bookmark_id in bookmark_ids:
        db.execute(
            "UPDATE bookmarks SET sync_status = 'synced', last_synced_at = ? WHERE id = ?",
            (now_iso, bookmark_id),
        )


def _mark_bookmarks_error(
    db: Database, bookmarks: list[dict[str, Any]], exclude_ids: list[int]
) -> None:
    excluded = set(exclude_ids)
    for bookmark in bookmarks:
        if bookmark["id"] not in excluded:
            db.execute(
                "UPDATE bookmarks SET sync_status = 'error' WHERE id = ?",
                (bookmark["id"],),
            )


def _mark_bookmark_pending_local(db: Database, bookmark_id: int) -> None:
    db.execute(
        "UPDATE bookmarks SET sync_status = 'pending_local' WHERE id = ?",
        (bookmark_id,),
    )


def _touch_synced_bookmarks(db: Database, synced_at: datetime) -> None:
    db.execute(
        "UPDATE bookmarks SET last_synced_at = ? WHERE sync_status = 'synced'",
        (synced_at.isoformat(),),
    )


def _validate_post(post: Mapping[str, Any]) -> dict[str, Any]:
    required_fields = ("href", "description", "hash", "time")
    missing = [field for field in required_fields if not post.get(field)]
    if missing:
        raise InvalidPinboardPostError(
            f"Pinboard post missing required field(s): {', '.join(missing)}"
        )
    return dict(post)


def _parse_tags(tags: object) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        return tags.split()
    if isinstance(tags, list):
        return [str(tag) for tag in tags]
    raise InvalidPinboardPostError("Pinboard post tags must be a string or list")


def _fetch_existing_mirror_bookmark(
    db: Database, remote: Mapping[str, Any]
) -> Any | None:
    row = db.execute(
        "SELECT id, created_at FROM bookmarks WHERE hash = ?", (remote["hash"],)
    ).fetchone()
    if row is None:
        row = _fetch_bookmark_identity_by_href(db, remote["href"])
    return row


def _fetch_bookmark_identity_by_href(db: Database, href: str) -> Any | None:
    return db.execute(
        "SELECT id, created_at FROM bookmarks WHERE href = ?", (href,)
    ).fetchone()


def _insert_synced_bookmark(
    db: Database, remote: Mapping[str, Any], synced_at: str
) -> None:
    db.execute(
        """
        INSERT INTO bookmarks (
            hash, href, description, extended, meta, time,
            shared, toread, sync_status, last_synced_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?)
        """,
        (
            remote["hash"],
            remote["href"],
            remote["description"],
            remote.get("extended", ""),
            remote.get("meta", ""),
            remote["time"],
            parse_boolean(remote.get("shared", "yes")),
            parse_boolean(remote.get("toread", "no")),
            synced_at,
        ),
    )


def _replace_synced_bookmark(
    db: Database,
    bookmark_id: int,
    remote: Mapping[str, Any],
    synced_at: str,
    created_at: str,
) -> None:
    db.execute(
        """
        DELETE FROM bookmarks
        WHERE id = ?
        """,
        (bookmark_id,),
    )
    db.execute(
        """
        INSERT INTO bookmarks (
            id, hash, href, description, extended, meta, time,
            shared, toread, sync_status, last_synced_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?, ?)
        """,
        (
            bookmark_id,
            remote["hash"],
            remote["href"],
            remote["description"],
            remote.get("extended", ""),
            remote.get("meta", ""),
            remote["time"],
            parse_boolean(remote.get("shared", "yes")),
            parse_boolean(remote.get("toread", "no")),
            synced_at,
            created_at,
        ),
    )


def _clear_local_mirror_pending_state(
    db: Database, bookmark_id: int, synced_at: str
) -> None:
    db.execute(
        """
        UPDATE bookmarks
        SET sync_status = 'synced',
            tags_modified = 0,
            original_tags = NULL,
            last_synced_at = ?
        WHERE id = ?
        """,
        (synced_at, bookmark_id),
    )


def _fetch_mirrored_bookmark(db: Database, bookmark_id: int) -> Any | None:
    return db.execute(
        "SELECT * FROM bookmarks_with_tags WHERE id = ?", (bookmark_id,)
    ).fetchone()
