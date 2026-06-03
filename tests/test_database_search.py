# ABOUTME: Tests for bookmark full-text search behavior and FTS index maintenance
# ABOUTME: Covers search query tokenization, raw input safety, and FTS triggers

import os
import tempfile
from collections.abc import Generator

import pytest

from pinboard_tools.database.models import Database, init_database
from pinboard_tools.database.queries import search_bookmarks


@pytest.fixture
def db() -> Generator[Database, None, None]:
    """Create a temporary database session for search tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    init_database(db_path)
    session = Database(db_path)
    session.connect()

    try:
        yield session
    finally:
        session.close()
        if os.path.exists(db_path):
            os.unlink(db_path)


def add_bookmark(
    db: Database,
    *,
    hash_: str,
    href: str,
    description: str,
    time: str,
    extended: str | None = None,
    tags: tuple[str, ...] = (),
) -> int:
    """Insert a bookmark and optional normalized tags."""
    cursor = db.execute(
        """
        INSERT INTO bookmarks (hash, href, description, extended, time)
        VALUES (?, ?, ?, ?, ?)
        """,
        (hash_, href, description, extended, time),
    )
    bookmark_id = int(cursor.lastrowid)

    for tag in tags:
        db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
        tag_id = db.execute("SELECT id FROM tags WHERE name = ?", (tag,)).fetchone()[
            "id"
        ]
        db.execute(
            "INSERT INTO bookmark_tags (bookmark_id, tag_id) VALUES (?, ?)",
            (bookmark_id, tag_id),
        )

    db.commit()
    return bookmark_id


def test_search_bookmarks_uses_full_text_tokens_not_substrings(db: Database) -> None:
    add_bookmark(
        db,
        hash_="python_hash",
        href="https://docs.python.org/3/",
        description="Python documentation",
        extended="Language reference and standard library",
        time="2024-03-01T00:00:00Z",
        tags=("docs", "python"),
    )

    token_results = search_bookmarks(db, "python")
    substring_results = search_bookmarks(db, "ytho")

    assert [row["hash"] for row in token_results] == ["python_hash"]
    assert substring_results == []


def test_search_bookmarks_searches_href_description_and_extended(
    db: Database,
) -> None:
    add_bookmark(
        db,
        hash_="href_hash",
        href="https://example.com/sqlite-guide",
        description="Reference",
        extended=None,
        time="2024-03-01T00:00:00Z",
    )
    add_bookmark(
        db,
        hash_="description_hash",
        href="https://example.com/reference",
        description="Queue internals",
        extended=None,
        time="2024-03-02T00:00:00Z",
    )
    add_bookmark(
        db,
        hash_="extended_hash",
        href="https://example.com/notes",
        description="Architecture notes",
        extended="Durable queue implementation",
        time="2024-03-03T00:00:00Z",
    )

    results = search_bookmarks(db, "queue OR sqlite")

    assert [row["hash"] for row in results] == [
        "extended_hash",
        "description_hash",
        "href_hash",
    ]


def test_search_bookmarks_treats_fts_expression_syntax_as_search_text(
    db: Database,
) -> None:
    add_bookmark(
        db,
        hash_="operator_hash",
        href="https://example.com/operators",
        description="Python NOT Ruby syntax notes",
        extended=None,
        time="2024-03-01T00:00:00Z",
    )

    results = search_bookmarks(db, "python NOT ruby")

    assert [row["hash"] for row in results] == ["operator_hash"]


def test_search_bookmarks_preserves_public_shape_order_and_tags(
    db: Database,
) -> None:
    add_bookmark(
        db,
        hash_="older_hash",
        href="https://example.com/older",
        description="Python guide",
        extended=None,
        time="2024-03-01T00:00:00Z",
        tags=("python", "guide"),
    )
    add_bookmark(
        db,
        hash_="newer_hash",
        href="https://example.com/newer",
        description="Python guide",
        extended=None,
        time="2024-03-02T00:00:00Z",
        tags=("python", "reference"),
    )

    results = search_bookmarks(db, "python")

    assert list(results[0].keys()) == ["hash", "href", "description", "time", "tags"]
    assert [row["hash"] for row in results] == ["newer_hash", "older_hash"]
    assert results[0]["tags"] == "python reference"


@pytest.mark.parametrize(
    "raw_query",
    [
        "https://example.com/path",
        "c++",
        "foo-bar",
    ],
)
def test_search_bookmarks_handles_raw_user_input_without_operational_error(
    db: Database, raw_query: str
) -> None:
    add_bookmark(
        db,
        hash_="special_hash",
        href="https://example.com/path",
        description="C++ foo-bar notes",
        extended=None,
        time="2024-03-01T00:00:00Z",
    )

    search_bookmarks(db, raw_query)


def test_bookmarks_fts_index_reflects_updates(db: Database) -> None:
    bookmark_id = add_bookmark(
        db,
        hash_="update_hash",
        href="https://example.com/update",
        description="Python notes",
        extended=None,
        time="2024-03-01T00:00:00Z",
    )

    db.execute(
        "UPDATE bookmarks SET description = ? WHERE id = ?",
        ("Ruby notes", bookmark_id),
    )
    db.commit()

    stale_rows = db.execute(
        "SELECT rowid FROM bookmarks_fts WHERE bookmarks_fts MATCH ?",
        ("python",),
    ).fetchall()
    updated_rows = db.execute(
        "SELECT rowid FROM bookmarks_fts WHERE bookmarks_fts MATCH ?",
        ("ruby",),
    ).fetchall()

    assert stale_rows == []
    assert [row["rowid"] for row in updated_rows] == [bookmark_id]


def test_bookmarks_fts_index_reflects_deletes(db: Database) -> None:
    bookmark_id = add_bookmark(
        db,
        hash_="delete_hash",
        href="https://example.com/delete",
        description="Python notes",
        extended=None,
        time="2024-03-01T00:00:00Z",
    )

    db.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
    db.commit()

    deleted_rows = db.execute(
        "SELECT rowid FROM bookmarks_fts WHERE bookmarks_fts MATCH ?",
        ("python",),
    ).fetchall()

    assert deleted_rows == []


def test_schema_migration_repairs_existing_fts_triggers_and_rebuilds_index(
    tmp_path,
) -> None:
    db_path = tmp_path / "bookmarks.db"
    db = Database(str(db_path))
    db.init_schema()

    bookmark_id = add_bookmark(
        db,
        hash_="migration_hash",
        href="https://example.com/migration",
        description="Python migration notes",
        extended=None,
        time="2024-03-01T00:00:00Z",
    )
    db.execute("UPDATE schema_version SET version = 2")
    db.execute("DROP TRIGGER bookmarks_fts_update")
    db.execute("DROP TRIGGER bookmarks_fts_delete")
    db.execute(
        """
        CREATE TRIGGER bookmarks_fts_update AFTER UPDATE ON bookmarks
        BEGIN
            UPDATE bookmarks_fts
            SET href = new.href,
                description = new.description,
                extended = new.extended
            WHERE rowid = new.id;
        END
        """
    )
    db.execute(
        """
        CREATE TRIGGER bookmarks_fts_delete AFTER DELETE ON bookmarks
        BEGIN
            DELETE FROM bookmarks_fts WHERE rowid = old.id;
        END
        """
    )
    db.execute("DELETE FROM bookmarks_fts")
    db.commit()
    db.close()

    migrated_db = Database(str(db_path))
    migrated_db.init_schema()
    migrated_db.execute(
        "UPDATE bookmarks SET description = ? WHERE id = ?",
        ("Ruby migration notes", bookmark_id),
    )
    migrated_db.commit()

    stale_rows = migrated_db.execute(
        "SELECT rowid FROM bookmarks_fts WHERE bookmarks_fts MATCH ?",
        ("python",),
    ).fetchall()
    updated_rows = migrated_db.execute(
        "SELECT rowid FROM bookmarks_fts WHERE bookmarks_fts MATCH ?",
        ("ruby",),
    ).fetchall()
    version = migrated_db.execute("SELECT version FROM schema_version").fetchone()[
        "version"
    ]

    assert version == 3
    assert stale_rows == []
    assert [row["rowid"] for row in updated_rows] == [bookmark_id]


def test_init_schema_is_idempotent_for_existing_database(tmp_path) -> None:
    db_path = tmp_path / "bookmarks.db"
    db = Database(str(db_path))

    db.init_schema()
    db.init_schema()

    version = db.execute("SELECT version FROM schema_version").fetchone()["version"]

    assert version == 3
