from __future__ import annotations

import importlib.util
from pathlib import Path

import pinboard_tools.database.models as database_models


def test_obsolete_migrations_module_is_not_importable() -> None:
    assert importlib.util.find_spec("pinboard_tools.database.migrations") is None


def test_unused_row_converters_are_not_database_model_attributes() -> None:
    assert not hasattr(database_models, "tag_from_row")
    assert not hasattr(database_models, "bookmark_tag_from_row")


def test_database_api_docs_do_not_publish_removed_helpers() -> None:
    database_api_docs = Path("docs/api/database.rst").read_text(encoding="utf-8")

    assert "tag_from_row" not in database_api_docs
    assert "bookmark_tag_from_row" not in database_api_docs
