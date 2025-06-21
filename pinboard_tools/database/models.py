# ABOUTME: Database models and schema definitions for Pinboard bookmarks
# ABOUTME: Defines the SQLite database structure and common queries

import importlib.resources as pkg_resources
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, TypedDict


class SyncStatus(Enum):
    """Sync status enumeration"""

    SYNCED = "synced"
    PENDING_LOCAL = "pending_local"
    PENDING_REMOTE = "pending_remote"
    CONFLICT = "conflict"


@dataclass
class Bookmark:
    """Bookmark model representing a Pinboard bookmark"""

    id: int | None = None
    href: str = ""
    description: str = ""
    extended: str | None = None
    meta: str | None = None
    hash: str | None = None
    time: datetime | str = ""
    shared: bool = True
    toread: bool = False
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    sync_status: str = SyncStatus.SYNCED.value
    last_synced_at: datetime | str | None = None
    tags_modified: bool = False
    original_tags: str | None = None
    # Tags are stored in normalized form, use get_bookmark_tags() to retrieve
    _tags: list[str] | None = None


@dataclass
class Tag:
    """Tag model for bookmark categorization"""

    id: int | None = None
    name: str = ""
    created_at: datetime | str | None = None


@dataclass
class BookmarkTag:
    """Bookmark-Tag relationship model"""

    bookmark_id: int
    tag_id: int
    created_at: datetime | str | None = None


@dataclass
class TagMerge:
    """Record of tag merge operations"""

    id: int | None = None
    old_tag: str = ""
    new_tag: str = ""
    merged_at: datetime | str | None = None
    bookmarks_updated: int = 0


# TypedDict versions for database query results
class BookmarkRow(TypedDict, total=False):
    """Type definition for bookmark database rows"""

    id: int
    href: str
    description: str
    extended: str | None
    meta: str | None
    hash: str
    time: str
    shared: int
    toread: int
    created_at: str
    updated_at: str
    sync_status: str
    last_synced_at: str | None
    tags_modified: int
    original_tags: str | None
    # tags field only present in views that generate it dynamically
    tags: str | None


class TagRow(TypedDict, total=False):
    """Type definition for tag database rows"""

    id: int
    name: str
    created_at: str


class BookmarkTagRow(TypedDict):
    """Type definition for bookmark_tag junction table rows"""

    bookmark_id: int
    tag_id: int
    created_at: str | None


class TagMergeRow(TypedDict):
    """Type definition for tag merge history rows"""

    id: int
    old_tag: str
    new_tag: str
    merged_at: str
    bookmarks_updated: int


class Database:
    """Database connection and query management"""

    def __init__(self, db_path: str = "bookmarks.db"):
        self.db_path = db_path
        self.connection: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Get or create database connection"""
        if self.connection is None:
            try:
                self.connection = sqlite3.connect(self.db_path)
                self.connection.row_factory = sqlite3.Row
                # Enable foreign key constraints
                self.connection.execute("PRAGMA foreign_keys = ON")
            except sqlite3.Error as e:
                raise sqlite3.DatabaseError(
                    f"Failed to connect to database at {self.db_path}: {e}"
                ) from e
        return self.connection

    def close(self) -> None:
        """Close database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None

    def init_schema(self) -> None:
        """Initialize database schema from schema.sql file"""
        conn = self.connect()

        # Access schema.sql as package data using modern importlib.resources API
        try:
            files = pkg_resources.files("pinboard_tools.data")
            schema_sql = (files / "schema.sql").read_text(encoding="utf-8")
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Schema file not found in package data: {e}"
            ) from e

        conn.executescript(schema_sql)
        conn.commit()

    def execute(self, query: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        """Execute a query and return cursor"""
        conn = self.connect()
        return conn.execute(query, params)

    def executemany(
        self, query: str, params_list: list[tuple[object, ...]]
    ) -> sqlite3.Cursor:
        """Execute many queries"""
        conn = self.connect()
        return conn.executemany(query, params_list)

    def commit(self) -> None:
        """Commit transaction"""
        if self.connection:
            self.connection.commit()

    def rollback(self) -> None:
        """Rollback transaction"""
        if self.connection:
            self.connection.rollback()

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()

    def enter_sync_context(self) -> None:
        """Mark that a sync operation is in progress to prevent triggers from firing"""
        self.execute(
            "INSERT OR REPLACE INTO sync_context (key, value) VALUES ('in_sync', 1)"
        )
        self.commit()

    def exit_sync_context(self) -> None:
        """Mark that sync operation is complete and triggers should fire normally"""
        self.execute("DELETE FROM sync_context WHERE key = 'in_sync'")
        self.commit()


# Convenience functions
_db_instance: Database | None = None


def init_database(db_path: str = "bookmarks.db") -> None:
    """Initialize the database with schema"""
    global _db_instance
    _db_instance = Database(db_path)
    _db_instance.init_schema()


def get_session() -> Database:
    """Get the current database session"""
    global _db_instance
    if _db_instance is None:
        init_database()
    assert _db_instance is not None
    return _db_instance


# Helper functions for converting between database rows and dataclass instances
def bookmark_from_row(row: dict[str, Any] | BookmarkRow) -> Bookmark:
    """Convert database row to Bookmark dataclass"""
    # Handle tags if present in view queries
    tags_list = None
    tags_value = row.get("tags")
    if tags_value:
        tags_list = tags_value.split()

    return Bookmark(
        id=row.get("id"),
        href=row.get("href", ""),
        description=row.get("description", ""),
        extended=row.get("extended"),
        meta=row.get("meta"),
        hash=row.get("hash"),
        time=row.get("time", ""),
        shared=bool(row.get("shared", True)),
        toread=bool(row.get("toread", False)),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
        sync_status=row.get("sync_status", SyncStatus.SYNCED.value),
        last_synced_at=row.get("last_synced_at"),
        tags_modified=bool(row.get("tags_modified", False)),
        original_tags=row.get("original_tags"),
        _tags=tags_list,
    )


def tag_from_row(row: dict[str, Any] | TagRow) -> Tag:
    """Convert database row to Tag dataclass"""
    return Tag(
        id=row.get("id"),
        name=row.get("name", ""),
        created_at=row.get("created_at"),
    )


def bookmark_tag_from_row(row: dict[str, Any] | BookmarkTagRow) -> BookmarkTag:
    """Convert database row to BookmarkTag dataclass"""
    return BookmarkTag(
        bookmark_id=row["bookmark_id"],
        tag_id=row["tag_id"],
        created_at=row.get("created_at"),
    )


# Tag utility functions
def get_bookmark_tags(db: Database, bookmark_id: int) -> list[str]:
    """Get tags for a bookmark as a list of strings"""
    cursor = db.execute(
        """
        SELECT t.name
        FROM tags t
        JOIN bookmark_tags bt ON t.id = bt.tag_id
        WHERE bt.bookmark_id = ?
        ORDER BY t.name
    """,
        (bookmark_id,),
    )
    return [row["name"] for row in cursor.fetchall()]


def get_bookmark_tags_string(db: Database, bookmark_id: int) -> str:
    """Get tags for a bookmark as a space-separated string for Pinboard API"""
    tags = get_bookmark_tags(db, bookmark_id)
    return " ".join(tags)


def set_bookmark_tags(db: Database, bookmark_id: int, tags: list[str]) -> None:
    """Set tags for a bookmark (replaces existing tags)"""
    # Normalize tags (strip whitespace, convert to lowercase, deduplicate)
    normalized_tags = list(set(tag.strip().lower() for tag in tags if tag.strip()))

    # Clear existing tags
    db.execute("DELETE FROM bookmark_tags WHERE bookmark_id = ?", (bookmark_id,))

    if normalized_tags:
        # Ensure all tags exist
        tag_params: list[tuple[object, ...]] = [(tag,) for tag in normalized_tags]
        db.executemany("INSERT OR IGNORE INTO tags (name) VALUES (?)", tag_params)

        # Get tag IDs
        placeholders = ",".join("?" * len(normalized_tags))
        cursor = db.execute(
            f"SELECT id, name FROM tags WHERE name IN ({placeholders})",
            tuple(normalized_tags),
        )
        tag_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        # Create bookmark-tag relationships
        bookmark_tag_params: list[tuple[object, ...]] = [
            (bookmark_id, tag_map[tag]) for tag in normalized_tags if tag in tag_map
        ]
        db.executemany(
            "INSERT INTO bookmark_tags (bookmark_id, tag_id) VALUES (?, ?)",
            bookmark_tag_params,
        )


def bookmark_with_tags(db: Database, bookmark_id: int) -> Bookmark | None:
    """Get a bookmark with its tags populated"""
    cursor = db.execute(
        "SELECT * FROM bookmarks_with_tags WHERE id = ?", (bookmark_id,)
    )
    row = cursor.fetchone()
    if row:
        return bookmark_from_row(dict(row))
    return None
