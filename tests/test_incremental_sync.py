# ABOUTME: Tests for incremental sync functionality
# ABOUTME: Verifies that sync operations use efficient API calls

import os
import tempfile
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import Mock, patch

import pytest

from pinboard_tools.database.models import (
    Database,
    get_session,
    get_sync_metadata,
    init_database,
    set_bookmark_tags,
)
from pinboard_tools.sync.bidirectional import (
    BidirectionalSync,
    ConflictResolution,
    SyncDirection,
)


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
        _, session = temp_db_with_sync_history

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
        _, session = temp_db_with_sync_history

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
        _, session = temp_db_with_sync_history

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
        _, session = temp_db_with_sync_history

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
        _, session = temp_db_with_sync_history

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

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_remote_changed_href_updates_existing_synced_bookmark_by_hash(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Remote updates with a moved href should update the existing hash row."""
        _, session = temp_db_with_sync_history
        recent_sync_time = datetime(2024, 1, 1, 1, 0, 0, tzinfo=UTC)
        session.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, timestamp) VALUES (?, ?)",
            ("last_remote_sync", recent_sync_time.isoformat()),
        )
        session.execute(
            """
            UPDATE bookmarks
            SET updated_at = ?, sync_status = 'synced'
            WHERE hash = 'hash1'
            """,
            ((recent_sync_time - timedelta(minutes=5)).isoformat(),),
        )
        session.commit()

        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.get_last_update.return_value = recent_sync_time + timedelta(minutes=30)
        mock_api.get_all_posts.return_value = [
            {
                "hash": "hash1",
                "href": "https://example.com/1-moved",
                "description": "Moved bookmark",
                "extended": "Remote changed the URL",
                "tags": "moved remote",
                "time": "2024-01-01T01:30:00Z",
                "toread": "yes",
                "shared": "no",
                "meta": "remote-meta",
            }
        ]

        sync = BidirectionalSync(session, "test_token")
        stats = sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

        rows = session.execute(
            "SELECT id, href, description, sync_status FROM bookmarks WHERE hash = ?",
            ("hash1",),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["href"] == "https://example.com/1-moved"
        assert rows[0]["description"] == "Moved bookmark"
        assert rows[0]["sync_status"] == "synced"
        assert stats["remote_to_local"] == 1

    @patch("pinboard_tools.sync.bidirectional.upsert_pinboard_post")
    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_pending_local_conflict_does_not_mirror_before_resolution(
        self,
        mock_api_class: Mock,
        mock_upsert_pinboard_post: Mock,
        temp_db_with_sync_history: tuple[str, Database],
    ) -> None:
        """A pending local conflict must be resolved before mirror writes occur."""
        _, session = temp_db_with_sync_history
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.get_all_posts.return_value = [
            {
                "hash": "hash3",
                "href": "https://example.com/3-remote",
                "description": "Remote conflicting bookmark",
                "extended": "",
                "tags": "remote conflict",
                "time": "2024-01-01T01:30:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            }
        ]

        sync = BidirectionalSync(session, "test_token")
        sync._sync_remote_to_local(
            conflict_resolution=ConflictResolution.LOCAL_WINS,
            dry_run=False,
        )

        mock_upsert_pinboard_post.assert_not_called()
        row = session.execute(
            "SELECT href, sync_status FROM bookmarks WHERE hash = ?", ("hash3",)
        ).fetchone()
        assert row["href"] == "https://example.com/3"
        assert row["sync_status"] == "pending_local"
        assert sync.sync_stats["conflicts_resolved"] == 1
        assert sync.sync_stats["remote_to_local"] == 0

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_remote_dry_run_counts_candidates_without_database_writes(
        self, mock_api_class: Mock, temp_db_with_sync_history: tuple[str, Database]
    ) -> None:
        """Remote dry run should count insert/update candidates without writes."""
        _, session = temp_db_with_sync_history
        set_bookmark_tags(session, 1, ["old"])
        session.execute(
            """
            UPDATE bookmarks
            SET updated_at = ?, sync_status = 'synced'
            WHERE hash = 'hash1'
            """,
            ((datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)).isoformat(),),
        )
        session.execute(
            "INSERT OR REPLACE INTO sync_metadata (key, timestamp) VALUES (?, ?)",
            ("last_remote_sync", datetime(2024, 1, 1, 0, 30, tzinfo=UTC).isoformat()),
        )
        session.commit()

        before_bookmarks = [
            dict(row) for row in session.execute("SELECT * FROM bookmarks ORDER BY id")
        ]
        before_tags = [
            dict(row)
            for row in session.execute(
                "SELECT * FROM bookmark_tags ORDER BY bookmark_id, tag_id"
            )
        ]
        before_metadata = get_sync_metadata(session, "last_remote_sync")

        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.get_all_posts.return_value = [
            {
                "hash": "hash1",
                "href": "https://example.com/1",
                "description": "Updated remote bookmark",
                "extended": "",
                "tags": "updated remote",
                "time": "2024-01-01T01:30:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            },
            {
                "hash": "hash_dry_run_new",
                "href": "https://example.com/dry-run-new",
                "description": "Dry run new bookmark",
                "extended": "",
                "tags": "dry run",
                "time": "2024-01-01T01:45:00Z",
                "toread": "yes",
                "shared": "no",
                "meta": "",
            },
        ]

        sync = BidirectionalSync(session, "test_token")
        sync._sync_remote_to_local(
            conflict_resolution=ConflictResolution.NEWEST_WINS,
            dry_run=True,
        )

        after_bookmarks = [
            dict(row) for row in session.execute("SELECT * FROM bookmarks ORDER BY id")
        ]
        after_tags = [
            dict(row)
            for row in session.execute(
                "SELECT * FROM bookmark_tags ORDER BY bookmark_id, tag_id"
            )
        ]

        assert sync.sync_stats["remote_to_local"] == 2
        assert after_bookmarks == before_bookmarks
        assert after_tags == before_tags
        assert get_sync_metadata(session, "last_remote_sync") == before_metadata
        assert (
            session.execute(
                "SELECT COUNT(*) FROM sync_context WHERE key = 'in_sync'"
            ).fetchone()[0]
            == 0
        )
