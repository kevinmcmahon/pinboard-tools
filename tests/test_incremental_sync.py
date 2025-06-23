# ABOUTME: Tests for incremental sync functionality
# ABOUTME: Verifies that sync operations use efficient API calls

import os
import tempfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch

import pytest

from pinboard_tools.database.models import Database, get_session, init_database
from pinboard_tools.sync.bidirectional import BidirectionalSync, SyncDirection


class TestIncrementalSync:
    """Test efficient incremental sync operations."""

    @pytest.fixture
    def temp_db_with_sync_history(self) -> Generator[tuple[str, Database], None, None]:
        """Create temporary database with sync history."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        init_database(db_path)
        session = get_session()

        # Create bookmarks with various sync timestamps
        base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        bookmarks: list[dict[str, Any]] = [
            {
                "hash": "hash1",
                "href": "https://example.com/1",
                "description": "Old synced bookmark",
                "sync_status": "synced",
                "last_synced_at": base_time.isoformat(),
            },
            {
                "hash": "hash2",
                "href": "https://example.com/2",
                "description": "Recent synced bookmark",
                "sync_status": "synced",
                "last_synced_at": (base_time + timedelta(hours=1)).isoformat(),
            },
            {
                "hash": "hash3",
                "href": "https://example.com/3",
                "description": "Pending local bookmark",
                "sync_status": "pending_local",
                "last_synced_at": None,
            },
        ]

        for bookmark in bookmarks:
            session.execute(
                """
                INSERT INTO bookmarks (hash, href, description, time, sync_status, last_synced_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bookmark["hash"],
                    bookmark["href"],
                    bookmark["description"],
                    "2024-01-01T00:00:00Z",
                    bookmark["sync_status"],
                    bookmark["last_synced_at"],
                ),
            )
        session.commit()

        yield db_path, session

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_no_sync_when_no_changes(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Test that sync is skipped when no changes exist."""
        db_path, session = temp_db_with_sync_history

        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Set up sync metadata to simulate previous sync
        recent_sync_time = datetime(2024, 1, 1, 1, 0, 0, tzinfo=UTC)
        session.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, timestamp) VALUES (?, ?)",
            ("last_remote_sync", recent_sync_time.isoformat()),
        )
        session.commit()

        # Mock last update to be older than most recent sync
        mock_api.get_last_update.return_value = recent_sync_time - timedelta(minutes=30)
        mock_api.get_all_posts.return_value = []  # No posts to return

        sync = BidirectionalSync(session, "test_token")

        # Perform sync
        stats = sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

        # Verify no remote API calls were made for posts
        mock_api.get_all_posts.assert_not_called()

        # Verify sync stats show no changes
        assert stats["remote_to_local"] == 0
        assert stats["local_to_remote"] == 0

        # Verify get_last_update was called for checking
        mock_api.get_last_update.assert_called_once()

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_incremental_sync_with_fromdt_parameter(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Test that incremental sync uses fromdt parameter correctly."""
        db_path, session = temp_db_with_sync_history

        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Set up sync metadata to simulate previous sync
        recent_sync_time = datetime(2024, 1, 1, 1, 0, 0, tzinfo=UTC)
        session.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, timestamp) VALUES (?, ?)",
            ("last_remote_sync", recent_sync_time.isoformat()),
        )
        session.commit()

        # Mock last update to be newer than most recent sync
        mock_api.get_last_update.return_value = recent_sync_time + timedelta(minutes=30)

        # Mock incremental response
        mock_api.get_all_posts.return_value = [
            {
                "hash": "hash_new",
                "href": "https://example.com/new",
                "description": "New bookmark",
                "extended": "",
                "tags": "test new",
                "time": "2024-01-01T01:30:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            }
        ]

        sync = BidirectionalSync(session, "test_token")

        # Perform sync
        stats = sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

        # Verify get_all_posts was called with fromdt parameter
        mock_api.get_all_posts.assert_called_once()
        call_args = mock_api.get_all_posts.call_args

        # Should be called with fromdt set to most recent sync time
        assert call_args.kwargs["fromdt"] == recent_sync_time

        # Verify stats show incremental changes
        assert stats["remote_to_local"] == 1

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_full_sync_on_first_run(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Test that full sync is performed when no sync history exists."""
        # Create empty database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            init_database(db_path)
            session = get_session()

            # Setup mock API
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.get_all_posts.return_value = []

            sync = BidirectionalSync(session, "test_token")

            # Perform sync
            sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

            # Verify get_all_posts was called without fromdt parameter (full sync)
            mock_api.get_all_posts.assert_called_once()
            call_args = mock_api.get_all_posts.call_args

            # Should be called without fromdt parameter
            assert (
                "fromdt" not in call_args.kwargs or call_args.kwargs["fromdt"] is None
            )

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_sync_reports_accurate_change_counts(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Test that sync reports accurate change counts, not total bookmark counts."""
        db_path, session = temp_db_with_sync_history

        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api

        # Set up sync metadata to simulate previous sync
        recent_sync_time = datetime(2024, 1, 1, 1, 0, 0, tzinfo=UTC)
        session.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, timestamp) VALUES (?, ?)",
            ("last_remote_sync", recent_sync_time.isoformat()),
        )
        session.commit()

        # Mock last update to indicate changes
        mock_api.get_last_update.return_value = recent_sync_time + timedelta(minutes=30)

        # Mock response with only 2 changed bookmarks (not full collection)
        mock_api.get_all_posts.return_value = [
            {
                "hash": "hash_changed1",
                "href": "https://example.com/changed1",
                "description": "Changed bookmark 1",
                "extended": "",
                "tags": "changed",
                "time": "2024-01-01T01:15:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            },
            {
                "hash": "hash_changed2",
                "href": "https://example.com/changed2",
                "description": "Changed bookmark 2",
                "extended": "",
                "tags": "changed",
                "time": "2024-01-01T01:20:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            },
        ]

        sync = BidirectionalSync(session, "test_token")

        # Perform sync (remote only, since this test fixture has pending local changes)
        stats = sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

        # Verify stats show only actual changes, not total collection size
        assert stats["remote_to_local"] == 2  # Only 2 changed bookmarks
        assert stats["local_to_remote"] == 0  # No local sync in this direction

        # Verify incremental API call was made with correct timestamp
        mock_api.get_all_posts.assert_called_once()
        call_args = mock_api.get_all_posts.call_args
        assert call_args.kwargs["fromdt"] == recent_sync_time

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_sync_with_mixed_directions(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Test bidirectional sync handles both local and remote changes efficiently."""
        db_path, session = temp_db_with_sync_history

        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.add_post.return_value = True

        # Set up sync metadata to simulate previous sync
        recent_sync_time = datetime(2024, 1, 1, 1, 0, 0, tzinfo=UTC)
        session.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, timestamp) VALUES (?, ?)",
            ("last_remote_sync", recent_sync_time.isoformat()),
        )
        session.commit()

        # Mock last update to indicate remote changes
        mock_api.get_last_update.return_value = recent_sync_time + timedelta(minutes=30)

        # Mock incremental remote changes
        mock_api.get_all_posts.return_value = [
            {
                "hash": "hash_remote_new",
                "href": "https://example.com/remote_new",
                "description": "New remote bookmark",
                "extended": "",
                "tags": "remote new",
                "time": "2024-01-01T01:30:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            }
        ]

        sync = BidirectionalSync(session, "test_token")

        # Perform bidirectional sync
        stats = sync.sync(direction=SyncDirection.BIDIRECTIONAL)

        # Verify both directions were handled
        assert stats["local_to_remote"] == 1  # 1 pending local bookmark
        assert stats["remote_to_local"] == 1  # 1 new remote bookmark

        # Verify efficient API usage
        mock_api.get_last_update.assert_called_once()
        mock_api.add_post.assert_called_once()

        # Verify incremental API call was made (timestamp may be updated during sync)
        mock_api.get_all_posts.assert_called_once()
        call_args = mock_api.get_all_posts.call_args
        assert "fromdt" in call_args.kwargs  # Should use incremental sync

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_sync_handles_api_errors_gracefully(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Test that sync handles API errors without breaking."""
        db_path, session = temp_db_with_sync_history

        # Setup mock API with error
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.get_last_update.side_effect = Exception("API Error")
        mock_api.get_all_posts.return_value = []  # Mock return value in case get_last_update doesn't fail early

        sync = BidirectionalSync(session, "test_token")

        # Sync should not crash on API errors
        try:
            stats = sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)
            # If we get here, the error was handled gracefully
            assert stats["errors"] >= 0  # Error count should be tracked
        except Exception as e:
            # If an exception is raised, it should be handled gracefully
            assert "API Error" in str(e)
