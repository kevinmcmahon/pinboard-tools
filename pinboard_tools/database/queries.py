# ABOUTME: Common database queries and statistics functions
# ABOUTME: Provides reusable queries for bookmarks and tags

from typing import Any

from .models import Database


def get_bookmark_count(db: Database) -> int:
    """Get total number of bookmarks"""
    cursor = db.execute("SELECT COUNT(*) as count FROM bookmarks")
    result = cursor.fetchone()
    return int(result["count"]) if result else 0


def get_top_tags(db: Database, limit: int = 20) -> list[dict[str, Any]]:
    """Get most used tags with counts"""
    cursor = db.execute(
        """
        SELECT t.name, COUNT(bt.bookmark_id) as count
        FROM tags t
        JOIN bookmark_tags bt ON t.id = bt.tag_id
        GROUP BY t.id
        ORDER BY count DESC
        LIMIT ?
    """,
        (limit,),
    )
    return [dict(row) for row in cursor]


def get_recent_bookmarks(db: Database, limit: int = 10) -> list[dict[str, Any]]:
    """Get most recently added bookmarks"""
    cursor = db.execute(
        """
        SELECT hash, href, description, time, tags
        FROM bookmarks
        ORDER BY time DESC
        LIMIT ?
    """,
        (limit,),
    )
    return [dict(row) for row in cursor]


def get_unread_bookmarks(
    db: Database, limit: int | None = None
) -> list[dict[str, Any]]:
    """Get bookmarks marked as unread"""
    query = """
        SELECT hash, href, description, time, tags
        FROM bookmarks
        WHERE toread = 1
        ORDER BY time DESC
    """
    params: tuple[object, ...] = ()

    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)

    cursor = db.execute(query, params)
    return [dict(row) for row in cursor]


def get_bookmarks_by_tag(db: Database, tag_name: str) -> list[dict[str, Any]]:
    """Get all bookmarks with a specific tag"""
    cursor = db.execute(
        """
        SELECT b.hash, b.href, b.description, b.time, b.tags
        FROM bookmarks b
        JOIN bookmark_tags bt ON b.id = bt.bookmark_id
        JOIN tags t ON bt.tag_id = t.id
        WHERE t.name = ?
        ORDER BY b.time DESC
    """,
        (tag_name,),
    )
    return [dict(row) for row in cursor]


def get_modified_bookmarks(
    db: Database, status: str | None = None
) -> list[dict[str, Any]]:
    """Get bookmarks with pending changes"""
    if status:
        cursor = db.execute(
            """
            SELECT id, hash, href, description, tags, sync_status, updated_at
            FROM bookmarks
            WHERE sync_status = ?
            ORDER BY updated_at DESC
        """,
            (status,),
        )
    else:
        cursor = db.execute("""
            SELECT id, hash, href, description, tags, sync_status, updated_at
            FROM bookmarks
            WHERE sync_status != 'synced'
            ORDER BY updated_at DESC
        """)
    return [dict(row) for row in cursor]


def search_bookmarks(db: Database, query: str) -> list[dict[str, Any]]:
    """Search bookmarks by description or URL"""
    search_term = f"%{query}%"
    cursor = db.execute(
        """
        SELECT hash, href, description, time, tags
        FROM bookmarks
        WHERE description LIKE ? OR href LIKE ? OR extended LIKE ?
        ORDER BY time DESC
    """,
        (search_term, search_term, search_term),
    )
    return [dict(row) for row in cursor]


def get_tag_stats(db: Database) -> dict[str, Any]:
    """Get comprehensive tag statistics"""
    stats = {}

    # Total unique tags
    cursor = db.execute("SELECT COUNT(*) as count FROM tags")
    stats["total_tags"] = cursor.fetchone()["count"]

    # Tags with no bookmarks
    cursor = db.execute("""
        SELECT COUNT(*) as count
        FROM tags t
        LEFT JOIN bookmark_tags bt ON t.id = bt.tag_id
        WHERE bt.tag_id IS NULL
    """)
    stats["unused_tags"] = cursor.fetchone()["count"]

    # Average tags per bookmark
    cursor = db.execute("""
        SELECT AVG(tag_count) as avg_tags
        FROM (
            SELECT COUNT(bt.tag_id) as tag_count
            FROM bookmarks b
            LEFT JOIN bookmark_tags bt ON b.id = bt.bookmark_id
            GROUP BY b.id
        )
    """)
    stats["avg_tags_per_bookmark"] = round(cursor.fetchone()["avg_tags"] or 0, 2)

    return stats
