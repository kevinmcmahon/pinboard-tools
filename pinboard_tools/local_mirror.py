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
        db.execute(
            """
            INSERT INTO bookmarks (
                hash, href, description, extended, meta, time,
                shared, toread, sync_status, last_synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?)
            ON CONFLICT(href) DO UPDATE SET
                hash = excluded.hash,
                description = excluded.description,
                extended = excluded.extended,
                meta = excluded.meta,
                time = excluded.time,
                shared = excluded.shared,
                toread = excluded.toread,
                sync_status = 'synced',
                last_synced_at = excluded.last_synced_at
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

        row = db.execute(
            "SELECT id FROM bookmarks WHERE href = ?", (remote["href"],)
        ).fetchone()
        if row is None:
            raise InvalidPinboardPostError(
                f"Mirrored bookmark could not be found: {remote['href']}"
            )

        bookmark_id = int(row["id"])
        set_bookmark_tags(db, bookmark_id, tags)
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
        db.commit()
    finally:
        db.exit_sync_context()

    mirrored = db.execute(
        "SELECT * FROM bookmarks_with_tags WHERE href = ?", (remote["href"],)
    ).fetchone()
    if mirrored is None:
        raise InvalidPinboardPostError(
            f"Mirrored bookmark could not be loaded: {remote['href']}"
        )
    return bookmark_from_row(dict(mirrored))


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
