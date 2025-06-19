# ABOUTME: Integration tests for complete tag normalization workflows
# ABOUTME: Tests end-to-end scenarios with the new tag architecture

import os
import tempfile
from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest

from pinboard_tools.analysis.consolidation import TagConsolidator
from pinboard_tools.database.models import (
    bookmark_with_tags,
    get_bookmark_tags,
    get_bookmark_tags_string,
    get_session,
    init_database,
    set_bookmark_tags,
)
from pinboard_tools.sync.bidirectional import BidirectionalSync, SyncDirection


class TestTagNormalizationIntegration:
    """Integration tests for complete tag normalization workflows."""

    @pytest.fixture
    def temp_db_integration(self) -> Generator[str, None, None]:
        """Create temporary database for integration testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        init_database(db_path)
        yield db_path

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_complete_tag_workflow(self, temp_db_integration: str) -> None:
        """Test complete workflow: create bookmarks, set tags, consolidate, query."""
        session = get_session()

        # Step 1: Create bookmarks with various tag patterns
        bookmarks_data = [
            {
                "hash": "workflow_1",
                "href": "https://python.org",
                "description": "Python Official Site",
                "tags": ["Python", "PROGRAMMING", "  documentation  "],
            },
            {
                "hash": "workflow_2",
                "href": "https://docs.python.org",
                "description": "Python Docs",
                "tags": ["python3", "Documentation", "reference"],
            },
            {
                "hash": "workflow_3",
                "href": "https://flask.palletsprojects.com",
                "description": "Flask Framework",
                "tags": ["python", "web", "framework"],
            },
        ]

        # Create bookmarks and set tags
        bookmark_ids = []
        for bookmark in bookmarks_data:
            session.execute(
                """
                INSERT INTO bookmarks (hash, href, description, time, sync_status)
                VALUES (?, ?, ?, ?, 'synced')
                """,
                (
                    bookmark["hash"],
                    bookmark["href"],
                    bookmark["description"],
                    "2024-01-01T00:00:00Z",
                ),
            )
            session.commit()

            result = session.execute(
                "SELECT id FROM bookmarks WHERE hash = ?", (bookmark["hash"],)
            )
            bookmark_id = result.fetchone()["id"]
            bookmark_ids.append(bookmark_id)

            # Set tags (should normalize automatically)
            set_bookmark_tags(session, bookmark_id, list(bookmark["tags"]))
            session.commit()

        # Step 2: Verify tag normalization occurred
        tags_1 = get_bookmark_tags(session, bookmark_ids[0])
        assert sorted(tags_1) == ["documentation", "programming", "python"]

        tags_2 = get_bookmark_tags(session, bookmark_ids[1])
        assert sorted(tags_2) == ["documentation", "python3", "reference"]

        tags_3 = get_bookmark_tags(session, bookmark_ids[2])
        assert sorted(tags_3) == ["framework", "python", "web"]

        # Step 3: Perform tag consolidation
        consolidator = TagConsolidator(session)

        # Merge python3 into python
        merge_result = consolidator.merge_tags("python3", "python", dry_run=False)
        assert merge_result["success"] is True
        assert merge_result["bookmarks_updated"] == 1

        # Step 4: Verify consolidation results
        tags_2_after = get_bookmark_tags(session, bookmark_ids[1])
        assert sorted(tags_2_after) == ["documentation", "python", "reference"]
        assert "python3" not in tags_2_after

        # Step 5: Test querying with consolidated tags
        # Find all python bookmarks
        cursor = session.execute("""
            SELECT b.id, b.description
            FROM bookmarks b
            JOIN bookmark_tags bt ON b.id = bt.bookmark_id
            JOIN tags t ON bt.tag_id = t.id
            WHERE t.name = 'python'
        """)
        python_bookmarks = cursor.fetchall()
        assert len(python_bookmarks) == 3  # All bookmarks should have python tag now

        # Step 6: Test tag string generation for API
        for bookmark_id in bookmark_ids:
            tags_string = get_bookmark_tags_string(session, bookmark_id)
            assert isinstance(tags_string, str)
            assert "python" in tags_string

    @patch("pinboard_tools.sync.bidirectional.PinboardAPI")
    def test_sync_workflow_with_tag_normalization(
        self, mock_api_class: Any, temp_db_integration: str
    ) -> None:
        """Test complete sync workflow with tag normalization."""
        # Setup mock API
        mock_api = Mock()
        mock_api_class.return_value = mock_api
        mock_api.add_post.return_value = True
        mock_api.get_last_update.return_value = None
        mock_api.get_all_posts.return_value = [
            {
                "hash": "remote_1",
                "href": "https://remote.example.com",
                "description": "Remote Bookmark",
                "extended": "",
                "tags": "Python  WEB   development",  # Messy formatting
                "time": "2024-01-01T12:00:00Z",
                "toread": "no",
                "shared": "yes",
                "meta": "",
            }
        ]

        session = get_session()

        # Step 1: Create local bookmark needing sync
        session.execute(
            """
            INSERT INTO bookmarks (hash, href, description, time, sync_status)
            VALUES (?, ?, ?, ?, 'pending_local')
            """,
            (
                "local_1",
                "https://local.example.com",
                "Local Bookmark",
                "2024-01-01T10:00:00Z",
            ),
        )
        session.commit()

        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("local_1",)
        )
        local_bookmark_id = result.fetchone()["id"]

        # Set tags for local bookmark
        set_bookmark_tags(
            session, local_bookmark_id, ["JavaScript", "frontend", "Tutorial"]
        )
        session.commit()

        # Step 2: Perform bidirectional sync
        sync = BidirectionalSync(session, "test_token")
        sync.sync(direction=SyncDirection.BIDIRECTIONAL, dry_run=False)

        # Step 3: Verify local to remote sync sent normalized tags
        mock_api.add_post.assert_called_once()
        call_args = mock_api.add_post.call_args
        assert (
            call_args.kwargs["tags"] == "frontend javascript tutorial"
        )  # Normalized and sorted

        # Step 4: Verify remote to local sync normalized incoming tags
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("remote_1",)
        )
        remote_bookmark_id = result.fetchone()["id"]

        remote_tags = get_bookmark_tags(session, remote_bookmark_id)
        assert sorted(remote_tags) == ["development", "python", "web"]  # Normalized

    def test_bookmark_with_tags_integration(self, temp_db_integration: str) -> None:
        """Test bookmark_with_tags function in complete workflow."""
        session = get_session()

        # Create bookmark
        session.execute(
            """
            INSERT INTO bookmarks (hash, href, description, extended, time, shared, toread)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "integration_test",
                "https://integration.example.com",
                "Integration Test Bookmark",
                "Extended description here",
                "2024-01-01T00:00:00Z",
                True,
                False,
            ),
        )
        session.commit()

        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("integration_test",)
        )
        bookmark_id = result.fetchone()["id"]

        # Set various tags
        tags = ["integration", "testing", "python", "automation"]
        set_bookmark_tags(session, bookmark_id, tags)
        session.commit()

        # Get bookmark with tags using utility function
        bookmark = bookmark_with_tags(session, bookmark_id)

        # Verify all data is present
        assert bookmark is not None
        assert bookmark.id == bookmark_id
        assert bookmark.description == "Integration Test Bookmark"
        assert bookmark.extended == "Extended description here"
        assert bookmark.shared is True
        assert bookmark.toread is False
        assert bookmark._tags is not None
        assert sorted(bookmark._tags) == [
            "automation",
            "integration",
            "python",
            "testing",
        ]

    def test_migration_scenario_string_to_normalized(
        self, temp_db_integration: str
    ) -> None:
        """Test scenario simulating migration from string-based to normalized tags."""
        session = get_session()

        # Simulate old-style bookmark that might have existed with string tags
        # (though our new schema doesn't have tags field, this tests the migration concept)
        session.execute(
            """
            INSERT INTO bookmarks (hash, href, description, time, sync_status)
            VALUES (?, ?, ?, ?, 'synced')
            """,
            (
                "migration_test",
                "https://migration.example.com",
                "Migration Test",
                "2024-01-01T00:00:00Z",
            ),
        )
        session.commit()

        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("migration_test",)
        )
        bookmark_id = result.fetchone()["id"]

        # Simulate migration: parse space-separated string and set normalized tags
        old_style_tags_string = "Python Web-Development API REST"
        old_style_tags = old_style_tags_string.split()

        # Set tags using new normalized approach
        set_bookmark_tags(session, bookmark_id, old_style_tags)
        session.commit()

        # Verify migration worked
        normalized_tags = get_bookmark_tags(session, bookmark_id)
        assert sorted(normalized_tags) == ["api", "python", "rest", "web-development"]

        # Verify we can generate API-compatible string
        api_string = get_bookmark_tags_string(session, bookmark_id)
        assert api_string == "api python rest web-development"

    def test_performance_with_many_tags(self, temp_db_integration: str) -> None:
        """Test performance characteristics with many tags and bookmarks."""
        session = get_session()

        # Create multiple bookmarks with overlapping tag sets
        num_bookmarks = 50
        tag_pool = [f"tag_{i}" for i in range(20)]  # 20 unique tags

        bookmark_ids = []
        for i in range(num_bookmarks):
            session.execute(
                """
                INSERT INTO bookmarks (hash, href, description, time)
                VALUES (?, ?, ?, ?)
                """,
                (
                    f"perf_test_{i}",
                    f"https://example.com/perf_{i}",
                    f"Performance Test Bookmark {i}",
                    "2024-01-01T00:00:00Z",
                ),
            )
            session.commit()

            result = session.execute(
                "SELECT id FROM bookmarks WHERE hash = ?", (f"perf_test_{i}",)
            )
            bookmark_id = result.fetchone()["id"]
            bookmark_ids.append(bookmark_id)

            # Assign 3-5 random tags to each bookmark
            import random

            bookmark_tags = random.sample(tag_pool, random.randint(3, 5))
            set_bookmark_tags(session, bookmark_id, bookmark_tags)
            session.commit()

        # Verify tag reuse efficiency
        result = session.execute("SELECT COUNT(*) as count FROM tags")
        total_tags = result.fetchone()["count"]
        assert total_tags == 20  # Should only have 20 unique tags despite 50 bookmarks

        # Test bulk tag operations
        result = session.execute("SELECT COUNT(*) as count FROM bookmark_tags")
        total_relationships = result.fetchone()["count"]
        assert total_relationships >= num_bookmarks * 3  # At least 3 tags per bookmark
        assert total_relationships <= num_bookmarks * 5  # At most 5 tags per bookmark

        # Test query performance (should be fast with proper indexes)
        cursor = session.execute("""
            SELECT b.id, COUNT(bt.tag_id) as tag_count
            FROM bookmarks b
            JOIN bookmark_tags bt ON b.id = bt.bookmark_id
            WHERE b.hash LIKE 'perf_test_%'
            GROUP BY b.id
            ORDER BY tag_count DESC
            LIMIT 10
        """)
        top_tagged = cursor.fetchall()
        assert len(top_tagged) == 10

    def test_edge_cases_integration(self, temp_db_integration: str) -> None:
        """Test edge cases in integrated tag workflow."""
        session = get_session()

        # Create bookmark for edge case testing
        session.execute(
            """
            INSERT INTO bookmarks (hash, href, description, time)
            VALUES (?, ?, ?, ?)
            """,
            (
                "edge_test",
                "https://edge.example.com",
                "Edge Case Test",
                "2024-01-01T00:00:00Z",
            ),
        )
        session.commit()

        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("edge_test",)
        )
        bookmark_id = result.fetchone()["id"]

        # Test empty tag list
        set_bookmark_tags(session, bookmark_id, [])
        session.commit()
        assert get_bookmark_tags(session, bookmark_id) == []
        assert get_bookmark_tags_string(session, bookmark_id) == ""

        # Test tags with special characters and Unicode
        special_tags = ["c++", "résumé", "日本語", "café", ".net", "node.js"]
        set_bookmark_tags(session, bookmark_id, special_tags)
        session.commit()

        retrieved_tags = get_bookmark_tags(session, bookmark_id)
        assert len(retrieved_tags) == 6
        assert "c++" in retrieved_tags
        assert "résumé" in retrieved_tags
        assert "日本語" in retrieved_tags

        # Test very long tag names
        long_tag = "a" * 200  # Very long tag
        set_bookmark_tags(session, bookmark_id, [long_tag, "short"])
        session.commit()

        retrieved_tags = get_bookmark_tags(session, bookmark_id)
        assert long_tag in retrieved_tags
        assert "short" in retrieved_tags

        # Test many tags on single bookmark
        many_tags = [f"tag_{i}" for i in range(100)]
        set_bookmark_tags(session, bookmark_id, many_tags)
        session.commit()

        retrieved_tags = get_bookmark_tags(session, bookmark_id)
        assert len(retrieved_tags) == 100
        assert all(f"tag_{i}" in retrieved_tags for i in range(100))

    def test_schema_consistency_check(self, temp_db_integration: str) -> None:
        """Test that schema changes maintain consistency."""
        session = get_session()

        # Verify all expected tables exist
        result = session.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in result.fetchall()]

        expected_tables = [
            "bookmarks",
            "tags",
            "bookmark_tags",
            "tag_merges",
            "bookmarks_fts",
        ]
        for table in expected_tables:
            assert table in tables

        # Verify foreign key constraints are enabled
        result = session.execute("PRAGMA foreign_keys")
        fk_enabled = result.fetchone()[0]
        assert fk_enabled == 1

        # Verify indexes exist for performance
        result = session.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        )
        indexes = [row["name"] for row in result.fetchall()]

        expected_indexes = [
            "idx_bookmarks_time",
            "idx_bookmarks_href",
            "idx_bookmarks_hash",
            "idx_tags_name",
            "idx_bookmark_tags_tag_id",
            "idx_bookmark_tags_bookmark_id",
        ]
        for index in expected_indexes:
            assert index in indexes
