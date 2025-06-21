# ABOUTME: Tests for sync operations with normalized tags
# ABOUTME: Covers bidirectional sync with the new tag architecture

import os
import tempfile
from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest

from pinboard_tools.database.models import (
    get_bookmark_tags,
    get_bookmark_tags_string,
    get_session,
    init_database,
    set_bookmark_tags,
)
from pinboard_tools.sync.bidirectional import BidirectionalSync, ConflictResolution


class TestSyncWithNormalizedTags:
    """Test sync operations with normalized tag storage."""

    @pytest.fixture
    def temp_db_with_bookmarks(self) -> Generator[str, None, None]:
        """Create temporary database with test bookmarks."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        init_database(db_path)
        session = get_session()

        # Create test bookmarks with different sync states
        bookmarks = [
            {
                "hash": "hash_pending",
                "href": "https://example.com/pending",
                "description": "Pending Local Bookmark",
                "sync_status": "pending_local",
                "tags": ["python", "flask"],
            },
            {
                "hash": "hash_synced",
                "href": "https://example.com/synced",
                "description": "Synced Bookmark",
                "sync_status": "synced",
                "tags": ["javascript", "react"],
            },
        ]

        for bookmark in bookmarks:
            # Insert bookmark
            session.execute(
                """
                INSERT INTO bookmarks (hash, href, description, time, sync_status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    bookmark["hash"],
                    bookmark["href"],
                    bookmark["description"],
                    "2024-01-01T00:00:00Z",
                    bookmark["sync_status"],
                ),
            )
            session.commit()

            # Get bookmark ID and set tags
            result = session.execute(
                "SELECT id FROM bookmarks WHERE hash = ?", (bookmark["hash"],)
            )
            bookmark_id = result.fetchone()["id"]
            set_bookmark_tags(session, bookmark_id, list(bookmark["tags"]))

            # Reset sync status if needed (triggers might have changed it)
            session.execute(
                "UPDATE bookmarks SET sync_status = ? WHERE id = ?",
                (bookmark["sync_status"], bookmark_id),
            )
            session.commit()

        yield db_path

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_local_to_remote_sync_with_tags(
        self, mock_api_class: Any, temp_db_with_bookmarks: str
    ) -> None:
        """Test syncing local changes to remote with normalized tags."""
        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.add_post.return_value = True

        session = get_session()
        sync = BidirectionalSync(session, "test_token")

        # Perform local to remote sync
        sync._sync_local_to_remote(dry_run=False)

        # Verify API was called with correct tag string
        mock_api.add_post.assert_called_once()
        call_args = mock_api.add_post.call_args

        # Verify the tags parameter is a properly formatted string
        assert (
            call_args.kwargs["tags"] == "flask python"
        )  # Should be sorted alphabetically
        assert call_args.kwargs["url"] == "https://example.com/pending"
        assert call_args.kwargs["description"] == "Pending Local Bookmark"

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_remote_to_local_sync_with_tags(
        self, mock_api_class: Any, temp_db_with_bookmarks: str
    ) -> None:
        """Test syncing remote changes to local with tag normalization."""
        # Setup mock API with remote post data
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Mock remote posts with tags
        remote_posts = [
            {
                "hash": "hash_new_remote",
                "href": "https://example.com/remote",
                "description": "Remote Bookmark",
                "extended": "",
                "tags": "Python  Web   API",  # Messy formatting to test normalization
                "time": "2024-01-01T12:00:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            }
        ]
        mock_api.get_all_posts.return_value = remote_posts

        session = get_session()
        sync = BidirectionalSync(session, "test_token")

        # Perform remote to local sync
        sync._sync_remote_to_local(
            conflict_resolution=ConflictResolution.NEWEST_WINS, dry_run=False
        )

        # Verify bookmark was inserted
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("hash_new_remote",)
        )
        bookmark_row = result.fetchone()
        assert bookmark_row is not None
        bookmark_id = bookmark_row["id"]

        # Verify tags were normalized and stored correctly
        tags = get_bookmark_tags(session, bookmark_id)
        assert sorted(tags) == [
            "api",
            "python",
            "web",
        ]  # Should be normalized (lowercase)

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_tag_update_from_remote(
        self, mock_api_class: Any, temp_db_with_bookmarks: str
    ) -> None:
        """Test updating existing bookmark tags from remote."""
        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Mock remote post with updated tags for existing bookmark
        remote_posts = [
            {
                "hash": "hash_synced",  # Existing bookmark
                "href": "https://example.com/synced",
                "description": "Synced Bookmark",
                "extended": "",
                "tags": "javascript vue testing",  # Changed from "react" to "vue", added "testing"
                "time": "2024-01-01T12:00:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            }
        ]
        mock_api.get_all_posts.return_value = remote_posts

        session = get_session()

        # Get bookmark ID for verification
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("hash_synced",)
        )
        bookmark_id = result.fetchone()["id"]

        # Verify original tags
        original_tags = get_bookmark_tags(session, bookmark_id)
        assert sorted(original_tags) == ["javascript", "react"]

        sync = BidirectionalSync(session, "test_token")

        # Perform remote to local sync
        sync._sync_remote_to_local(
            conflict_resolution=ConflictResolution.NEWEST_WINS, dry_run=False
        )

        # Verify tags were updated
        updated_tags = get_bookmark_tags(session, bookmark_id)
        assert sorted(updated_tags) == ["javascript", "testing", "vue"]

    def test_tag_string_generation_for_sync(self, temp_db_with_bookmarks: str) -> None:
        """Test that tag strings are generated correctly for API calls."""
        session = get_session()

        # Get a bookmark with tags
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("hash_pending",)
        )
        bookmark_id = result.fetchone()["id"]

        # Test tag string generation
        tags_string = get_bookmark_tags_string(session, bookmark_id)
        assert tags_string == "flask python"  # Should be alphabetically sorted

        # Test with different tag order
        set_bookmark_tags(session, bookmark_id, ["zebra", "alpha", "beta"])
        session.commit()

        tags_string = get_bookmark_tags_string(session, bookmark_id)
        assert tags_string == "alpha beta zebra"

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_empty_tags_sync(
        self, mock_api_class: Any, temp_db_with_bookmarks: str
    ) -> None:
        """Test syncing bookmarks with no tags."""
        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.add_post.return_value = True

        session = get_session()

        # Create bookmark with no tags
        session.execute(
            """
            INSERT INTO bookmarks (hash, href, description, time, sync_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "hash_no_tags",
                "https://example.com/notags",
                "Bookmark No Tags",
                "2024-01-01T00:00:00Z",
                "pending_local",
            ),
        )
        session.commit()

        sync = BidirectionalSync(session, "test_token")
        sync._sync_local_to_remote(dry_run=False)

        # Verify API was called with empty tags string
        mock_api.add_post.assert_called()
        call_args = mock_api.add_post.call_args
        assert call_args.kwargs["tags"] == ""

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_dry_run_with_tags(
        self, mock_api_class: Any, temp_db_with_bookmarks: str
    ) -> None:
        """Test dry run doesn't modify tags but reports correctly."""
        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.add_post.return_value = True

        session = get_session()

        # Get original tags
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("hash_pending",)
        )
        bookmark_id = result.fetchone()["id"]
        original_tags = get_bookmark_tags(session, bookmark_id)

        sync = BidirectionalSync(session, "test_token")

        # Perform dry run
        sync._sync_local_to_remote(dry_run=True)

        # Verify tags unchanged
        current_tags = get_bookmark_tags(session, bookmark_id)
        assert current_tags == original_tags

        # Verify API wasn't called
        mock_api.add_post.assert_not_called()

    def test_sync_status_trigger_on_tag_changes(
        self, temp_db_with_bookmarks: str
    ) -> None:
        """Test that tag changes trigger appropriate sync status updates."""
        session = get_session()

        # Get a synced bookmark
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ? AND sync_status = 'synced'",
            ("hash_synced",),
        )
        bookmark_id = result.fetchone()["id"]

        # Modify tags - should trigger sync status change
        set_bookmark_tags(session, bookmark_id, ["new", "tags"])
        session.commit()

        # Verify sync status changed
        result = session.execute(
            "SELECT sync_status FROM bookmarks WHERE id = ?", (bookmark_id,)
        )
        sync_status = result.fetchone()["sync_status"]
        assert sync_status == "pending_local"

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_special_characters_in_tags(
        self, mock_api_class: Any, temp_db_with_bookmarks: str
    ) -> None:
        """Test handling of special characters in tags during sync."""
        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Mock remote post with special characters in tags
        remote_posts = [
            {
                "hash": "hash_special_chars",
                "href": "https://example.com/special",
                "description": "Special Characters",
                "extended": "",
                "tags": "c++ .net café résumé",  # Various special characters
                "time": "2024-01-01T12:00:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            }
        ]
        mock_api.get_all_posts.return_value = remote_posts

        session = get_session()
        sync = BidirectionalSync(session, "test_token")

        # Perform remote to local sync
        sync._sync_remote_to_local(
            conflict_resolution=ConflictResolution.NEWEST_WINS, dry_run=False
        )

        # Verify bookmark was inserted with special character tags
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("hash_special_chars",)
        )
        bookmark_id = result.fetchone()["id"]

        # Verify tags with special characters are handled correctly
        tags = get_bookmark_tags(session, bookmark_id)
        assert "c++" in tags
        assert ".net" in tags
        assert "café" in tags
        assert "résumé" in tags

        # Test round trip - tags string should preserve special characters
        tags_string = get_bookmark_tags_string(session, bookmark_id)
        assert "c++" in tags_string
        assert ".net" in tags_string

    def test_tag_case_sensitivity_normalization(
        self, temp_db_with_bookmarks: str
    ) -> None:
        """Test that tag case normalization works consistently."""
        session = get_session()

        # Get a bookmark
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("hash_synced",)
        )
        bookmark_id = result.fetchone()["id"]

        # Set tags with mixed case
        mixed_case_tags = ["Python", "JAVASCRIPT", "Html", "css"]
        set_bookmark_tags(session, bookmark_id, mixed_case_tags)
        session.commit()

        # Verify all tags are normalized to lowercase
        normalized_tags = get_bookmark_tags(session, bookmark_id)
        assert sorted(normalized_tags) == ["css", "html", "javascript", "python"]

        # Verify case-insensitive deduplication
        duplicate_case_tags = ["python", "Python", "PYTHON"]
        set_bookmark_tags(session, bookmark_id, duplicate_case_tags)
        session.commit()

        # Should only have one instance
        deduped_tags = get_bookmark_tags(session, bookmark_id)
        assert deduped_tags == ["python"]

    def test_remote_sync_does_not_trigger_pending_status(
        self, temp_db_with_bookmarks: str
    ) -> None:
        """Test that syncing from remote doesn't mark bookmarks as pending_local.

        This test addresses the bug where database triggers incorrectly marked
        bookmarks as pending during legitimate remote sync operations, causing
        infinite sync loops.
        """
        # Use temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Initialize fresh database
            init_database(db_path)
            session = get_session()

            # Mock API to provide predictable test data (avoids network calls and external dependencies)
            mock_api = Mock()
            mock_api.get_all_posts.return_value = [
                {
                    "hash": "hash1",
                    "href": "http://example.com/1",
                    "description": "Bookmark with multiple tags",
                    "extended": "Extended description",
                    "meta": "meta1",
                    "time": "2024-01-01T00:00:00Z",
                    "shared": "yes",
                    "toread": "no",
                    "tags": "python flask web-development",
                },
                {
                    "hash": "hash2",
                    "href": "http://example.com/2",
                    "description": "Bookmark with no tags",
                    "extended": "",
                    "meta": "",
                    "time": "2024-01-01T01:00:00Z",
                    "shared": "no",
                    "toread": "yes",
                    "tags": "",
                },
                {
                    "hash": "hash3",
                    "href": "http://example.com/3",
                    "description": "Bookmark with special chars in tags",
                    "extended": "",
                    "meta": "",
                    "time": "2024-01-01T02:00:00Z",
                    "shared": "yes",
                    "toread": "no",
                    "tags": "c++ machine-learning data_science",
                },
            ]

            sync = BidirectionalSync(session, "test_token")
            sync.api = mock_api

            # Verify initial state: no bookmarks exist
            initial_count = session.execute(
                "SELECT COUNT(*) FROM bookmarks"
            ).fetchone()[0]
            assert initial_count == 0, "Database should start empty"

            # Perform remote sync
            sync._sync_remote_to_local(ConflictResolution.NEWEST_WINS, dry_run=False)

            # Critical assertion: no bookmarks should be marked as pending_local
            cursor = session.execute(
                "SELECT COUNT(*) FROM bookmarks WHERE sync_status = 'pending_local'"
            )
            pending_count = cursor.fetchone()[0]
            assert pending_count == 0, (
                f"Remote sync should not create pending_local bookmarks, got {pending_count}"
            )

            # All bookmarks should be properly synced
            cursor = session.execute(
                "SELECT COUNT(*) FROM bookmarks WHERE sync_status = 'synced'"
            )
            synced_count = cursor.fetchone()[0]
            expected_count = len(mock_api.get_all_posts.return_value)
            assert synced_count == expected_count, (
                f"Expected {expected_count} synced bookmarks, got {synced_count}"
            )

            # Verify tags_modified flag is not set for any bookmark
            cursor = session.execute(
                "SELECT COUNT(*) FROM bookmarks WHERE tags_modified = 1"
            )
            modified_count = cursor.fetchone()[0]
            assert modified_count == 0, (
                f"Remote sync should not set tags_modified flag, got {modified_count} bookmarks flagged"
            )

            # Verify sync context is properly cleaned up
            cursor = session.execute(
                "SELECT COUNT(*) FROM sync_context WHERE key = 'in_sync'"
            )
            context_count = cursor.fetchone()[0]
            assert context_count == 0, (
                "Sync context should be cleaned up after sync operation"
            )

        finally:
            # Clean up
            os.unlink(db_path)
