# ABOUTME: Tests for package integrity and schema.sql availability
# ABOUTME: Ensures schema file is accessible after package installation

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from pinboard_tools import init_database
from pinboard_tools.database.models import Database


class TestSchemaPackaging:
    """Test schema.sql packaging and accessibility"""

    def test_schema_file_accessible_in_development(self) -> None:
        """Test that schema.sql is accessible in development environment"""
        # This should work in development where schema.sql is at repo root
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
            temp_db_path = temp_db.name

        try:
            # This should succeed in development
            init_database(temp_db_path)

            # Verify database was created and has expected tables
            conn = sqlite3.connect(temp_db_path)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            expected_tables = ["bookmarks", "tags", "bookmark_tags"]
            for table in expected_tables:
                assert table in tables, f"Expected table '{table}' not found"

        finally:
            Path(temp_db_path).unlink(missing_ok=True)

    def test_schema_missing_simulates_installed_package(self) -> None:
        """Test that missing schema.sql raises FileNotFoundError (simulating installed package)"""
        # Simulate installed package scenario where schema.sql is not accessible
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
            temp_db_path = temp_db.name

        db = Database(temp_db_path)

        # Mock the importlib.resources to simulate missing package data
        with patch("pinboard_tools.database.models.pkg_resources.files") as mock_files:
            mock_files.side_effect = FileNotFoundError("No such package data")
            with pytest.raises(
                FileNotFoundError, match="Schema file not found in package data"
            ):
                db.init_schema()

        Path(temp_db_path).unlink(missing_ok=True)

    def test_init_database_fails_with_missing_schema(self) -> None:
        """Test that init_database() fails when schema.sql is missing"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
            temp_db_path = temp_db.name

        # Mock importlib.resources to simulate missing package data
        with patch("pinboard_tools.database.models.pkg_resources.files") as mock_files:
            mock_files.side_effect = FileNotFoundError("No such package data")
            with pytest.raises(
                FileNotFoundError, match="Schema file not found in package data"
            ):
                init_database(temp_db_path)

        Path(temp_db_path).unlink(missing_ok=True)

    def test_schema_path_resolution_logic(self) -> None:
        """Test the current schema path resolution logic"""
        # This is what the current code computes
        pinboard_tools_dir: Path = Path(__file__).parent.parent / "pinboard_tools"
        computed_schema_path: Path = pinboard_tools_dir / "data" / "schema.sql"

        # In development, this should exist
        assert computed_schema_path.exists(), (
            f"Schema not found at computed path: {computed_schema_path}"
        )

        # The issue: this path won't exist in installed packages
        # because schema.sql won't be included in the distribution

    def test_database_connection_without_schema_init(self) -> None:
        """Test that Database can connect but fails on operations without schema"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
            temp_db_path = temp_db.name

        try:
            db = Database(temp_db_path)

            # Connection should work
            conn = db.connect()
            assert conn is not None

            # But queries to non-existent tables should fail
            with pytest.raises(sqlite3.OperationalError, match="no such table"):
                db.execute("SELECT * FROM bookmarks")

        finally:
            db.close()
            Path(temp_db_path).unlink(missing_ok=True)

    def test_bug_report_exact_scenario(self) -> None:
        """Test the exact scenario described in the bug report"""
        # Simulate trying to use the library as described in bug report
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_db:
            temp_db_path = temp_db.name

        try:
            # This is the exact code from the bug report that should work:
            # from pinboard_tools import init_database
            # init_database("bookmarks.db")

            # Mock the scenario where schema.sql is missing (installed package)
            with patch(
                "pinboard_tools.database.models.pkg_resources.files"
            ) as mock_files:
                mock_files.side_effect = FileNotFoundError("No such package data")
                with pytest.raises(FileNotFoundError) as exc_info:
                    init_database(temp_db_path)

                # Verify it's the specific error mentioned in the bug report
                assert "Schema file not found in package data:" in str(exc_info.value)

        finally:
            Path(temp_db_path).unlink(missing_ok=True)
