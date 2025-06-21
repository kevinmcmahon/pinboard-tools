# ABOUTME: Main entry point for pinboard-tools library
# ABOUTME: Exports key classes and functions for Pinboard bookmark management

"""A Python library for syncing and managing Pinboard bookmarks."""

__version__ = "0.1.8"

from .analysis.consolidation import TagConsolidator

# Analysis tools
from .analysis.similarity import TagSimilarityDetector

# Database components
from .database.models import (
    Bookmark,
    BookmarkTag,
    SyncStatus,
    Tag,
    get_session,
    init_database,
)

# Sync functionality
from .sync.api import PinboardAPI
from .sync.bidirectional import BidirectionalSync

# Utilities
from .utils.chunking import chunk_bookmarks_for_llm
from .utils.datetime import format_pinboard_time, parse_pinboard_time

__all__ = [
    # Sync
    "BidirectionalSync",
    # Database
    "Bookmark",
    "BookmarkTag",
    "PinboardAPI",
    "SyncStatus",
    "Tag",
    # Analysis
    "TagConsolidator",
    "TagSimilarityDetector",
    # Utils
    "chunk_bookmarks_for_llm",
    "format_pinboard_time",
    "get_session",
    "init_database",
    "parse_pinboard_time",
]
