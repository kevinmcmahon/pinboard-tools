# pinboard-tools

[![PyPI version](https://img.shields.io/pypi/v/pinboard-tools.svg)](https://pypi.org/project/pinboard-tools/)
[![Python versions](https://img.shields.io/pypi/pyversions/pinboard-tools.svg)](https://pypi.org/project/pinboard-tools/)
[![License](https://img.shields.io/pypi/l/pinboard-tools.svg)](https://github.com/kevinmcmahon/pinboard-tools/blob/main/LICENSE)

A Python library for syncing and managing Pinboard bookmarks.

## Features

- **Efficient incremental sync** with Pinboard.in API (only fetches changed bookmarks)
- **Bidirectional sync** with configurable conflict resolution strategies
- **SQLite database** with normalized tag storage and full-text search
- **Thread-safe** database singleton with proper locking
- **Error recovery** for failed sync operations with retry support
- **Tag analysis** and similarity detection
- **Tag consolidation** for merging duplicate tags
- **Exponential backoff** on API rate limits with max retry protection
- **Rate limiting** and optimized API usage
- **Chunking utilities** for LLM processing

## Installation

```bash
pip install pinboard-tools
```

## Quick Start

```python
from pinboard_tools import (
    init_database,
    get_session,
    BidirectionalSync,
)

# Initialize database
init_database("bookmarks.db")

# Create sync engine
db = get_session()
sync = BidirectionalSync(db=db, api_token="your-pinboard-api-token")

# Perform efficient incremental sync
stats = sync.sync()
print(f"Local to remote: {stats['local_to_remote']}")
print(f"Remote to local: {stats['remote_to_local']}")
print(f"Conflicts resolved: {stats['conflicts_resolved']}")
```

## Core Components

### Database Models

- `Bookmark` - Bookmark entity with all Pinboard fields
- `Tag` - Tag entity with normalization
- `BookmarkTag` - Many-to-many relationship
- `SyncStatus` - Track sync state (`synced`, `pending_local`, `pending_remote`, `conflict`, `error`)

### Sync Engine

- `PinboardAPI` - API client with rate limiting, exponential backoff, and JSON error handling
- `BidirectionalSync` - Efficient incremental sync with conflict resolution and error recovery

### Tag Analysis

- `TagSimilarityDetector` - Find similar tags
- `TagConsolidator` - Merge duplicate tags

### Utilities

- `chunk_bookmarks_for_llm` - Prepare data for LLM processing
- DateTime helpers for Pinboard format

## Database Schema

The library uses a normalized SQLite schema with full-text search:

```sql
-- Core tables (see pinboard_tools/data/schema.sql for complete structure)
bookmarks (href, description, extended, hash, time, sync_status, ...)
tags (name)
bookmark_tags (bookmark_id, tag_id)
sync_metadata (key, timestamp)

-- Convenience view
bookmarks_with_tags  -- joins bookmarks with their tags as space-separated string
```

## API Reference

### Initialization

```python
# Initialize database with schema
init_database(db_path: str)

# Get database session
with get_session() as session:
    # Use session for queries
```

### Syncing

```python
# Create sync client
sync = BidirectionalSync(db=session, api_token="your-token")

# Efficient incremental sync (only fetches changed bookmarks)
stats = sync.sync()

# Sync only local changes to remote
stats = sync.sync(direction=SyncDirection.LOCAL_TO_REMOTE)

# Sync only remote changes to local
stats = sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

# Retry bookmarks that previously failed to sync
retried = sync.retry_failed_bookmarks()
if retried > 0:
    stats = sync.sync()  # re-sync the retried bookmarks
```

### Tag Analysis

```python
# Find similar tags
detector = TagSimilarityDetector(session)
similar_groups = detector.find_similar_tags(threshold=0.8)

# Consolidate tags
consolidator = TagConsolidator(session)
consolidator.consolidate_tags(old_tag="python3", new_tag="python")
```

## License

Apache License 2.0 - see LICENSE file for details