# ABOUTME: Tests for tag analysis and similarity detection
# ABOUTME: Covers tag similarity algorithms and consolidation logic

import os
import tempfile
from collections.abc import Generator

import pytest

from pinboard_tools.analysis.similarity import TagSimilarityDetector
from pinboard_tools.database.models import get_session, init_database


class TestTagAnalysis:
    """Test tag analysis functionality."""

    @pytest.fixture
    def temp_db_with_tags(self) -> Generator[str, None, None]:
        """Create temporary database with sample tags."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        init_database(db_path)

        # Add sample tags
        session = get_session()
        tag_names = [
            "python",
            "python3",
            "javascript",
            "js",
            "web-dev",
            "webdev",
            "development",
            "dev",
        ]
        for tag_name in tag_names:
            session.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        session.commit()

        yield db_path

        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_similarity_detector_init(self, temp_db_with_tags: str) -> None:
        """Test similarity detector initialization."""
        # Get tag names from database
        session = get_session()
        result = session.execute("SELECT name FROM tags")
        tag_names = [row["name"] for row in result.fetchall()]

        detector = TagSimilarityDetector(tag_names)
        assert len(detector.tags) > 0

    def test_find_similar_tags(self, temp_db_with_tags: str) -> None:
        """Test finding similar tags."""
        # Get tag names from database
        session = get_session()
        result = session.execute("SELECT name FROM tags")
        tag_names = [row["name"] for row in result.fetchall()]

        detector = TagSimilarityDetector(tag_names)
        similarities = detector.find_all_similarities(threshold=0.7)

        # Should find some similarities
        assert len(similarities) > 0

        # Check if we found similarities for python variants
        python_similarities = similarities.get("python", [])
        assert len(python_similarities) > 0

    def test_tag_normalization(self, temp_db_with_tags: str) -> None:
        """Test tag normalization for similarity."""
        detector = TagSimilarityDetector(["python", "Python", "javascript", "js"])

        # Test prefix/suffix relationship
        is_related = detector._is_prefix_suffix_related("python", "python3")
        assert is_related

        # Test abbreviation detection
        abbrevs = detector._get_common_abbreviations("javascript")
        assert "js" in abbrevs

    def test_empty_database(self, temp_db_with_tags: str) -> None:
        """Test similarity detection with empty database."""
        # Test with empty tag list
        detector = TagSimilarityDetector([])
        similarities = detector.find_all_similarities()

        # Should return empty dict for empty tag list
        assert similarities == {}
