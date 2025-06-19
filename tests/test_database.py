# ABOUTME: Tests for database models and operations
# ABOUTME: Covers database initialization, models, and queries

import os
import tempfile
from collections.abc import Generator

import pytest

from pinboard_tools.database.models import (
    get_session,
    init_database,
)


class TestDatabase:
    """Test database functionality."""

    @pytest.fixture
    def temp_db(self) -> Generator[str, None, None]:
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        init_database(db_path)
        yield db_path

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_init_database(self, temp_db: str) -> None:
        """Test database initialization."""
        # Database should exist and be accessible
        with get_session() as session:
            # Should be able to query tables
            result = session.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in result.fetchall()]

            expected_tables = {"bookmarks", "tags", "bookmark_tags"}
            assert expected_tables.issubset(set(tables))

            # Check for FTS tables
            assert "bookmarks_fts" in tables

    def test_create_bookmark(self, temp_db: str) -> None:
        """Test bookmark creation."""
        session = get_session()

        # Insert bookmark directly using SQL
        session.execute(
            "INSERT INTO bookmarks (hash, href, description, time) VALUES (?, ?, ?, ?)",
            (
                "test_hash",
                "https://example.com",
                "Test Bookmark",
                "2024-01-01T00:00:00Z",
            ),
        )
        session.commit()

        # Verify bookmark was created
        result = session.execute(
            "SELECT * FROM bookmarks WHERE href = ?", ("https://example.com",)
        )
        row = result.fetchone()
        assert row is not None
        assert row["description"] == "Test Bookmark"

    def test_create_tag(self, temp_db: str) -> None:
        """Test tag creation."""
        session = get_session()

        # Insert tag directly using SQL
        session.execute("INSERT INTO tags (name) VALUES (?)", ("python",))
        session.commit()

        # Verify tag was created
        result = session.execute("SELECT * FROM tags WHERE name = ?", ("python",))
        row = result.fetchone()
        assert row is not None
        assert row["name"] == "python"

    def test_bookmark_tag_relationship(self, temp_db: str) -> None:
        """Test many-to-many relationship between bookmarks and tags."""
        session = get_session()

        # Create bookmark and tag
        session.execute(
            "INSERT INTO bookmarks (hash, href, description, time) VALUES (?, ?, ?, ?)",
            (
                "test_hash",
                "https://example.com",
                "Test Bookmark",
                "2024-01-01T00:00:00Z",
            ),
        )
        session.execute("INSERT INTO tags (name) VALUES (?)", ("python",))
        session.commit()

        # Get IDs
        bookmark_result = session.execute(
            "SELECT id FROM bookmarks WHERE href = ?", ("https://example.com",)
        )
        bookmark_id = bookmark_result.fetchone()["id"]

        tag_result = session.execute("SELECT id FROM tags WHERE name = ?", ("python",))
        tag_id = tag_result.fetchone()["id"]

        # Create relationship
        session.execute(
            "INSERT INTO bookmark_tags (bookmark_id, tag_id) VALUES (?, ?)",
            (bookmark_id, tag_id),
        )
        session.commit()

        # Verify relationship
        result = session.execute("SELECT * FROM bookmark_tags")
        row = result.fetchone()
        assert row is not None
        assert row["bookmark_id"] == bookmark_id
        assert row["tag_id"] == tag_id

    def test_batch_tag_operations(self, temp_db: str) -> None:
        """Test batch tag operations for performance optimization."""
        session = get_session()

        # Create a bookmark
        session.execute(
            "INSERT INTO bookmarks (hash, href, description, time) VALUES (?, ?, ?, ?)",
            (
                "test_hash",
                "https://example.com",
                "Test Bookmark",
                "2024-01-01T00:00:00Z",
            ),
        )
        session.commit()

        # Get bookmark ID
        bookmark_result = session.execute(
            "SELECT id FROM bookmarks WHERE href = ?", ("https://example.com",)
        )
        bookmark_id = bookmark_result.fetchone()["id"]

        # Test batch tag insertion (simulating the optimized _update_bookmark_tags logic)
        tags = ["python", "programming", "web", "database", "api"]

        # Batch insert all tags
        tag_params: list[tuple[object, ...]] = [(tag,) for tag in tags]
        session.executemany("INSERT OR IGNORE INTO tags (name) VALUES (?)", tag_params)

        # Get all tag IDs in a single query
        placeholders = ",".join("?" * len(tags))
        cursor = session.execute(
            f"SELECT id, name FROM tags WHERE name IN ({placeholders})", tuple(tags)
        )
        tag_map = {row["name"]: row["id"] for row in cursor.fetchall()}

        # Batch insert bookmark-tag relationships
        bookmark_tag_params: list[tuple[object, ...]] = [
            (bookmark_id, tag_map[tag]) for tag in tags if tag in tag_map
        ]
        session.executemany(
            "INSERT INTO bookmark_tags (bookmark_id, tag_id) VALUES (?, ?)",
            bookmark_tag_params,
        )
        session.commit()

        # Verify all tags were created and linked
        result = session.execute(
            """
            SELECT t.name
            FROM tags t
            JOIN bookmark_tags bt ON t.id = bt.tag_id
            WHERE bt.bookmark_id = ?
            ORDER BY t.name
            """,
            (bookmark_id,),
        )
        linked_tags = [row["name"] for row in result.fetchall()]

        assert len(linked_tags) == 5
        assert set(linked_tags) == set(tags)
