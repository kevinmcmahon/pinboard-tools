# ABOUTME: Tests for tag utility functions and normalized tag handling
# ABOUTME: Covers the new tag normalization architecture and API functions

import os
import tempfile
from collections.abc import Generator

import pytest

from pinboard_tools.database.models import (
    bookmark_with_tags,
    get_bookmark_tags,
    get_bookmark_tags_string,
    get_session,
    init_database,
    set_bookmark_tags,
)


class TestTagUtilities:
    """Test tag utility functions with normalized storage."""

    @pytest.fixture
    def temp_db_with_bookmark(self) -> Generator[tuple[str, int], None, None]:
        """Create temporary database with a test bookmark."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        init_database(db_path)
        session = get_session()

        # Create a test bookmark
        session.execute(
            "INSERT INTO bookmarks (hash, href, description, time) VALUES (?, ?, ?, ?)",
            (
                "test_hash_123",
                "https://example.com/test",
                "Test Bookmark for Tags",
                "2024-01-01T00:00:00Z",
            ),
        )
        session.commit()

        # Get bookmark ID
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("test_hash_123",)
        )
        bookmark_id = result.fetchone()["id"]

        yield db_path, bookmark_id

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_set_bookmark_tags_basic(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test basic tag setting functionality."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Set some tags
        tags = ["python", "web", "development"]
        set_bookmark_tags(session, bookmark_id, tags)
        session.commit()

        # Verify tags were created in tags table
        result = session.execute("SELECT name FROM tags ORDER BY name")
        stored_tags = [row["name"] for row in result.fetchall()]
        assert stored_tags == ["development", "python", "web"]

        # Verify bookmark-tag relationships
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
        bookmark_tags = [row["name"] for row in result.fetchall()]
        assert bookmark_tags == ["development", "python", "web"]

    def test_set_bookmark_tags_normalization(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test tag normalization during setting."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Set tags with various formatting issues
        messy_tags = ["  Python  ", "WEB", "Development  ", "", "   ", "API"]
        set_bookmark_tags(session, bookmark_id, messy_tags)
        session.commit()

        # Verify normalization (lowercase, trimmed, empty removed)
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
        normalized_tags = [row["name"] for row in result.fetchall()]
        assert normalized_tags == ["api", "development", "python", "web"]

    def test_set_bookmark_tags_replacement(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test that setting tags replaces existing tags."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Set initial tags
        initial_tags = ["python", "flask"]
        set_bookmark_tags(session, bookmark_id, initial_tags)
        session.commit()

        # Set new tags (should replace, not append)
        new_tags = ["javascript", "react"]
        set_bookmark_tags(session, bookmark_id, new_tags)
        session.commit()

        # Verify only new tags are present
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
        current_tags = [row["name"] for row in result.fetchall()]
        assert current_tags == ["javascript", "react"]

        # Verify old tags still exist in tags table (might be used by other bookmarks)
        result = session.execute("SELECT name FROM tags ORDER BY name")
        all_tags = [row["name"] for row in result.fetchall()]
        assert "python" in all_tags
        assert "flask" in all_tags

    def test_get_bookmark_tags(self, temp_db_with_bookmark: tuple[str, int]) -> None:
        """Test getting bookmark tags as a list."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Set up tags
        tags = ["python", "web", "api"]
        set_bookmark_tags(session, bookmark_id, tags)
        session.commit()

        # Get tags back
        retrieved_tags = get_bookmark_tags(session, bookmark_id)
        assert sorted(retrieved_tags) == ["api", "python", "web"]

    def test_get_bookmark_tags_empty(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test getting tags for bookmark with no tags."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Don't set any tags
        retrieved_tags = get_bookmark_tags(session, bookmark_id)
        assert retrieved_tags == []

    def test_get_bookmark_tags_string(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test getting bookmark tags as space-separated string."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Set up tags
        tags = ["python", "web", "api"]
        set_bookmark_tags(session, bookmark_id, tags)
        session.commit()

        # Get tags as string
        tags_string = get_bookmark_tags_string(session, bookmark_id)
        # Should be sorted alphabetically
        assert tags_string == "api python web"

    def test_get_bookmark_tags_string_empty(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test getting tags string for bookmark with no tags."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Don't set any tags
        tags_string = get_bookmark_tags_string(session, bookmark_id)
        assert tags_string == ""

    def test_bookmark_with_tags(self, temp_db_with_bookmark: tuple[str, int]) -> None:
        """Test getting bookmark with tags populated."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Set up tags
        tags = ["python", "tutorial"]
        set_bookmark_tags(session, bookmark_id, tags)
        session.commit()

        # Get bookmark with tags
        bookmark = bookmark_with_tags(session, bookmark_id)
        assert bookmark is not None
        assert bookmark.id == bookmark_id
        assert bookmark.description == "Test Bookmark for Tags"
        assert bookmark._tags is not None
        assert sorted(bookmark._tags) == ["python", "tutorial"]

    def test_bookmark_with_tags_nonexistent(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test getting non-existent bookmark returns None."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Try to get non-existent bookmark
        bookmark = bookmark_with_tags(session, 99999)
        assert bookmark is None

    def test_multiple_bookmarks_same_tags(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test that multiple bookmarks can share the same tags efficiently."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Create another bookmark
        session.execute(
            "INSERT INTO bookmarks (hash, href, description, time) VALUES (?, ?, ?, ?)",
            (
                "test_hash_456",
                "https://example.com/test2",
                "Second Test Bookmark",
                "2024-01-02T00:00:00Z",
            ),
        )
        session.commit()

        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("test_hash_456",)
        )
        bookmark_id_2 = result.fetchone()["id"]

        # Set same tags for both bookmarks
        common_tags = ["python", "web"]
        set_bookmark_tags(session, bookmark_id, common_tags)
        set_bookmark_tags(session, bookmark_id_2, common_tags)
        session.commit()

        # Verify both bookmarks have the tags
        tags_1 = get_bookmark_tags(session, bookmark_id)
        tags_2 = get_bookmark_tags(session, bookmark_id_2)
        assert sorted(tags_1) == ["python", "web"]
        assert sorted(tags_2) == ["python", "web"]

        # Verify tags aren't duplicated in tags table
        result = session.execute(
            "SELECT COUNT(*) as count FROM tags WHERE name = 'python'"
        )
        python_count = result.fetchone()["count"]
        assert python_count == 1

        result = session.execute(
            "SELECT COUNT(*) as count FROM tags WHERE name = 'web'"
        )
        web_count = result.fetchone()["count"]
        assert web_count == 1

    def test_set_empty_tags(self, temp_db_with_bookmark: tuple[str, int]) -> None:
        """Test setting empty tag list clears all tags."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Set initial tags
        initial_tags = ["python", "web"]
        set_bookmark_tags(session, bookmark_id, initial_tags)
        session.commit()

        # Verify tags are set
        tags = get_bookmark_tags(session, bookmark_id)
        assert len(tags) == 2

        # Clear tags by setting empty list
        set_bookmark_tags(session, bookmark_id, [])
        session.commit()

        # Verify tags are cleared
        tags = get_bookmark_tags(session, bookmark_id)
        assert tags == []

    def test_tag_sync_status_trigger(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test that tag changes trigger sync status updates."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Verify initial sync status
        result = session.execute(
            "SELECT sync_status FROM bookmarks WHERE id = ?", (bookmark_id,)
        )
        initial_status = result.fetchone()["sync_status"]
        assert initial_status == "synced"

        # Set tags - should trigger sync status change
        tags = ["python", "web"]
        set_bookmark_tags(session, bookmark_id, tags)
        session.commit()

        # Verify sync status changed
        result = session.execute(
            "SELECT sync_status FROM bookmarks WHERE id = ?", (bookmark_id,)
        )
        new_status = result.fetchone()["sync_status"]
        assert new_status == "pending_local"

    def test_concurrent_tag_operations(
        self, temp_db_with_bookmark: tuple[str, int]
    ) -> None:
        """Test that concurrent tag operations work correctly."""
        db_path, bookmark_id = temp_db_with_bookmark
        session = get_session()

        # Create multiple bookmarks
        bookmark_ids = [bookmark_id]
        for i in range(2, 5):
            session.execute(
                "INSERT INTO bookmarks (hash, href, description, time) VALUES (?, ?, ?, ?)",
                (
                    f"test_hash_{i}",
                    f"https://example.com/test{i}",
                    f"Test Bookmark {i}",
                    "2024-01-01T00:00:00Z",
                ),
            )
            session.commit()

            result = session.execute(
                "SELECT id FROM bookmarks WHERE hash = ?", (f"test_hash_{i}",)
            )
            bookmark_ids.append(result.fetchone()["id"])

        # Set overlapping tags for different bookmarks
        tag_sets = [
            ["python", "web"],
            ["python", "api"],
            ["web", "frontend"],
            ["python", "backend"],
        ]

        for i, bid in enumerate(bookmark_ids):
            set_bookmark_tags(session, bid, tag_sets[i])
        session.commit()

        # Verify each bookmark has correct tags
        for i, bid in enumerate(bookmark_ids):
            tags = get_bookmark_tags(session, bid)
            assert sorted(tags) == sorted(tag_sets[i])

        # Verify tag reuse - should have unique tags in tags table
        result = session.execute("SELECT DISTINCT name FROM tags ORDER BY name")
        all_unique_tags = [row["name"] for row in result.fetchall()]
        expected_unique = sorted(set(tag for tag_set in tag_sets for tag in tag_set))
        assert all_unique_tags == expected_unique
