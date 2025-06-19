# ABOUTME: Tests for tag consolidation with normalized tag storage
# ABOUTME: Covers tag merging and analysis with the new architecture

import os
import tempfile
from collections.abc import Generator

import pytest

from pinboard_tools.analysis.consolidation import TagConsolidator
from pinboard_tools.database.models import (
    get_bookmark_tags,
    get_session,
    init_database,
    set_bookmark_tags,
)


class TestTagConsolidationWithNormalizedTags:
    """Test tag consolidation with normalized tag storage."""

    @pytest.fixture
    def temp_db_with_tag_data(self) -> Generator[str, None, None]:
        """Create temporary database with realistic tag consolidation test data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        init_database(db_path)
        session = get_session()

        # Create bookmarks with various tag patterns for consolidation testing
        # Make some tags much more popular to trigger consolidation suggestions
        test_data = [
            {
                "hash": "bookmark_1",
                "href": "https://example.com/1",
                "description": "Python Tutorial",
                "tags": ["python", "tutorial", "programming"],
            },
            {
                "hash": "bookmark_2",
                "href": "https://example.com/2",
                "description": "Python Guide",
                "tags": ["python", "guide", "programming"],
            },
            {
                "hash": "bookmark_3",
                "href": "https://example.com/3",
                "description": "Python Framework",
                "tags": ["python", "framework", "programming"],
            },
            {
                "hash": "bookmark_4",
                "href": "https://example.com/4",
                "description": "Python Advanced",
                "tags": ["python", "advanced", "programming"],
            },
            {
                "hash": "bookmark_5",
                "href": "https://example.com/5",
                "description": "Python3 Guide",
                "tags": [
                    "python3",
                    "guide",
                ],  # This should be suggested to merge with python
            },
            {
                "hash": "bookmark_6",
                "href": "https://example.com/6",
                "description": "JavaScript Tutorial",
                "tags": ["javascript", "tutorial", "web"],
            },
            {
                "hash": "bookmark_7",
                "href": "https://example.com/7",
                "description": "JavaScript Framework",
                "tags": ["javascript", "framework", "web"],
            },
            {
                "hash": "bookmark_8",
                "href": "https://example.com/8",
                "description": "JavaScript Advanced",
                "tags": ["javascript", "advanced", "web"],
            },
            {
                "hash": "bookmark_9",
                "href": "https://example.com/9",
                "description": "JS Basics",
                "tags": [
                    "js",
                    "tutorial",
                ],  # This should be suggested to merge with javascript
            },
            {
                "hash": "bookmark_10",
                "href": "https://example.com/10",
                "description": "Development Tools",
                "tags": ["development", "tools", "programming"],
            },
            {
                "hash": "bookmark_11",
                "href": "https://example.com/11",
                "description": "Dev Environment",
                "tags": [
                    "dev",
                    "environment",
                ],  # This should be suggested to merge with development
            },
            {
                "hash": "bookmark_12",
                "href": "https://example.com/12",
                "description": "Rare Tag Example",
                "tags": ["obscure-tag", "programming"],
            },
        ]

        for bookmark in test_data:
            # Insert bookmark
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

            # Get bookmark ID and set tags
            result = session.execute(
                "SELECT id FROM bookmarks WHERE hash = ?", (bookmark["hash"],)
            )
            bookmark_id = result.fetchone()["id"]
            set_bookmark_tags(session, bookmark_id, list(bookmark["tags"]))

            # Reset sync status to 'synced' (triggers might have changed it)
            session.execute(
                "UPDATE bookmarks SET sync_status = 'synced' WHERE id = ?",
                (bookmark_id,),
            )
            session.commit()

        yield db_path

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_tag_analysis_with_normalized_storage(
        self, temp_db_with_tag_data: str
    ) -> None:
        """Test tag analysis works with normalized tag storage."""
        session = get_session()
        consolidator = TagConsolidator(session)

        analysis = consolidator.analyze_tags()

        # Verify basic analysis structure
        assert "total_tags" in analysis
        assert "tags_with_counts" in analysis
        assert "similarities" in analysis
        assert "consolidation_suggestions" in analysis

        # Verify tag counts
        tags_with_counts = analysis["tags_with_counts"]
        assert tags_with_counts["programming"] == 6  # Used in 6 bookmarks (1-4, 10, 12)
        assert tags_with_counts["web"] == 3  # Used in 3 bookmarks (6-8)
        assert tags_with_counts["tutorial"] == 3  # Used in 3 bookmarks (1, 6, 9)

        # Verify similarities are found
        similarities = analysis["similarities"]
        assert len(similarities) > 0

    def test_merge_tags_with_normalized_storage(
        self, temp_db_with_tag_data: str
    ) -> None:
        """Test tag merging with normalized storage."""
        session = get_session()
        consolidator = TagConsolidator(session)

        # Get initial tag counts
        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'python3'"
        )
        python3_count = result.fetchone()["count"]
        assert python3_count == 1

        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'python'"
        )
        python_count = result.fetchone()["count"]
        assert python_count == 4

        # Merge python3 into python
        merge_result = consolidator.merge_tags("python3", "python", dry_run=False)

        assert merge_result["success"] is True
        assert merge_result["bookmarks_updated"] == 1

        # Verify python3 is gone from bookmark associations
        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'python3'"
        )
        python3_count_after = result.fetchone()["count"]
        assert python3_count_after == 0

        # Verify python now has all bookmarks (original 4 + merged 1)
        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'python'"
        )
        python_count_after = result.fetchone()["count"]
        assert python_count_after == 5

        # Verify the specific bookmark has the right tags
        result = session.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", ("bookmark_2",)
        )
        bookmark_id = result.fetchone()["id"]

        tags = get_bookmark_tags(session, bookmark_id)
        assert "python" in tags
        assert "python3" not in tags
        assert "guide" in tags
        assert "programming" in tags

    def test_merge_tags_dry_run(self, temp_db_with_tag_data: str) -> None:
        """Test dry run tag merging doesn't change data."""
        session = get_session()
        consolidator = TagConsolidator(session)

        # Get initial state
        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'js'"
        )
        js_count_before = result.fetchone()["count"]

        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'javascript'"
        )
        javascript_count_before = result.fetchone()["count"]

        # Perform dry run merge
        merge_result = consolidator.merge_tags("js", "javascript", dry_run=True)

        assert merge_result["success"] is True
        assert merge_result["bookmarks_updated"] == 1  # Would update 1 bookmark
        assert merge_result["dry_run"] is True

        # Verify nothing actually changed
        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'js'"
        )
        js_count_after = result.fetchone()["count"]
        assert js_count_after == js_count_before

        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'javascript'"
        )
        javascript_count_after = result.fetchone()["count"]
        assert javascript_count_after == javascript_count_before

    def test_merge_nonexistent_tag(self, temp_db_with_tag_data: str) -> None:
        """Test merging with nonexistent source tag."""
        session = get_session()
        consolidator = TagConsolidator(session)

        result = consolidator.merge_tags("nonexistent", "python", dry_run=False)

        assert result["success"] is False
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_merge_tags_sync_status_update(self, temp_db_with_tag_data: str) -> None:
        """Test that tag merging updates bookmark sync status."""
        session = get_session()
        consolidator = TagConsolidator(session)

        # Verify initial sync status
        result = session.execute(
            "SELECT sync_status FROM bookmarks WHERE hash = ?", ("bookmark_9",)
        )
        initial_status = result.fetchone()["sync_status"]
        assert initial_status == "synced"

        # Merge tags (js -> javascript)
        consolidator.merge_tags("js", "javascript", dry_run=False)

        # Verify sync status changed to pending_local
        result = session.execute(
            "SELECT sync_status FROM bookmarks WHERE hash = ?", ("bookmark_9",)
        )
        new_status = result.fetchone()["sync_status"]
        assert new_status == "pending_local"

    def test_merge_creates_tag_merge_record(self, temp_db_with_tag_data: str) -> None:
        """Test that tag merging creates a record in tag_merges table."""
        session = get_session()
        consolidator = TagConsolidator(session)

        # Verify no merge records initially
        result = session.execute("SELECT COUNT(*) as count FROM tag_merges")
        initial_count = result.fetchone()["count"]
        assert initial_count == 0

        # Perform merge
        consolidator.merge_tags("dev", "development", dry_run=False)

        # Verify merge record was created
        result = session.execute("SELECT COUNT(*) as count FROM tag_merges")
        final_count = result.fetchone()["count"]
        assert final_count == 1

        # Verify merge record details
        result = session.execute(
            "SELECT old_tag, new_tag, bookmarks_updated FROM tag_merges ORDER BY id DESC LIMIT 1"
        )
        merge_record = result.fetchone()
        assert merge_record["old_tag"] == "dev"
        assert merge_record["new_tag"] == "development"
        assert merge_record["bookmarks_updated"] == 1

    def test_consolidation_suggestions(self, temp_db_with_tag_data: str) -> None:
        """Test consolidation suggestions with normalized tags."""
        session = get_session()
        consolidator = TagConsolidator(session)

        analysis = consolidator.analyze_tags()
        suggestions = analysis["consolidation_suggestions"]

        # Should have suggestions for similar tags
        assert len(suggestions) > 0

        # Look for specific expected suggestions
        suggestion_types = [s["type"] for s in suggestions]
        assert (
            "merge_to_popular" in suggestion_types
            or "consolidate_rare" in suggestion_types
        )

        # Verify suggestion structure
        for suggestion in suggestions:
            assert "type" in suggestion
            assert "from" in suggestion
            assert "to" in suggestion
            assert "reason" in suggestion
            assert "from_count" in suggestion
            assert "to_count" in suggestion

    def test_co_occurrence_analysis(self, temp_db_with_tag_data: str) -> None:
        """Test tag co-occurrence analysis."""
        session = get_session()
        consolidator = TagConsolidator(session)

        co_occurrence = consolidator._analyze_co_occurrence(limit=10)

        # Should find some co-occurring tags
        assert len(co_occurrence) > 0

        # Verify structure
        for co_occur in co_occurrence:
            assert "tag1" in co_occur
            assert "tag2" in co_occur
            assert "count" in co_occur
            assert co_occur["count"] > 0

    def test_unused_tag_cleanup(self, temp_db_with_tag_data: str) -> None:
        """Test that unused tags are removed after merge."""
        session = get_session()
        consolidator = TagConsolidator(session)

        # Verify tag exists before merge
        result = session.execute(
            "SELECT COUNT(*) as count FROM tags WHERE name = 'obscure-tag'"
        )
        before_count = result.fetchone()["count"]
        assert before_count == 1

        # Create a new tag that will be unused after merge
        session.execute("INSERT INTO tags (name) VALUES (?)", ("temp-tag",))
        session.commit()

        # Merge obscure-tag into programming (which has multiple uses)
        consolidator.merge_tags("obscure-tag", "programming", dry_run=False)

        # Verify obscure-tag was removed from tags table (no longer used)
        result = session.execute(
            "SELECT COUNT(*) as count FROM tags WHERE name = 'obscure-tag'"
        )
        after_count = result.fetchone()["count"]
        assert after_count == 0

        # But temp-tag should still exist (not involved in merge)
        result = session.execute(
            "SELECT COUNT(*) as count FROM tags WHERE name = 'temp-tag'"
        )
        temp_count = result.fetchone()["count"]
        assert temp_count == 1

    def test_merge_into_new_tag(self, temp_db_with_tag_data: str) -> None:
        """Test merging into a tag that doesn't exist yet."""
        session = get_session()
        consolidator = TagConsolidator(session)

        # Verify target tag doesn't exist
        result = session.execute(
            "SELECT COUNT(*) as count FROM tags WHERE name = 'brand-new-tag'"
        )
        before_count = result.fetchone()["count"]
        assert before_count == 0

        # Merge into new tag
        merge_result = consolidator.merge_tags(
            "obscure-tag", "brand-new-tag", dry_run=False
        )
        assert merge_result["success"] is True

        # Verify new tag was created and has the bookmark
        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'brand-new-tag'"
        )
        new_tag_count = result.fetchone()["count"]
        assert new_tag_count == 1

        # Verify old tag is gone
        result = session.execute(
            "SELECT COUNT(*) as count FROM bookmark_tags bt JOIN tags t ON bt.tag_id = t.id WHERE t.name = 'obscure-tag'"
        )
        old_tag_count = result.fetchone()["count"]
        assert old_tag_count == 0
