-- ABOUTME: SQLite schema for storing Pinboard bookmarks with normalized tags
-- ABOUTME: Supports efficient tag-based searches and maintains all bookmark metadata

-- Main bookmarks table
CREATE TABLE bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    href TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    extended TEXT,
    meta TEXT,
    hash TEXT UNIQUE,
    time DATETIME NOT NULL,
    shared BOOLEAN NOT NULL DEFAULT 0,
    toread BOOLEAN NOT NULL DEFAULT 0,
    -- Change tracking columns for Pinboard sync
    tags_modified BOOLEAN DEFAULT 0,
    last_synced_at DATETIME,
    sync_status TEXT DEFAULT 'synced' CHECK(sync_status IN ('synced', 'pending_local', 'pending_remote', 'conflict', 'error')),
    original_tags TEXT,  -- Stores tags before modification for rollback
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Tags table for normalized tag storage
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Junction table for many-to-many relationship between bookmarks and tags
CREATE TABLE bookmark_tags (
    bookmark_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (bookmark_id, tag_id),
    FOREIGN KEY (bookmark_id) REFERENCES bookmarks(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- Tag merge history table
CREATE TABLE tag_merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    old_tag TEXT NOT NULL,
    new_tag TEXT NOT NULL,
    merged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    bookmarks_updated INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX idx_bookmarks_time ON bookmarks(time DESC);
CREATE INDEX idx_bookmarks_href ON bookmarks(href);
CREATE INDEX idx_bookmarks_hash ON bookmarks(hash);
CREATE INDEX idx_bookmarks_toread ON bookmarks(toread) WHERE toread = 1;
CREATE INDEX idx_bookmarks_tags_modified ON bookmarks(tags_modified) WHERE tags_modified = 1;
CREATE INDEX idx_bookmarks_sync_status ON bookmarks(sync_status) WHERE sync_status IN ('pending_local', 'pending_remote', 'conflict');
CREATE INDEX idx_tags_name ON tags(name);
CREATE INDEX idx_bookmark_tags_tag_id ON bookmark_tags(tag_id);
CREATE INDEX idx_bookmark_tags_bookmark_id ON bookmark_tags(bookmark_id);
CREATE INDEX idx_tag_merges_old_tag ON tag_merges(old_tag);
CREATE INDEX idx_tag_merges_new_tag ON tag_merges(new_tag);

-- Full-text search support for bookmark content
CREATE VIRTUAL TABLE bookmarks_fts USING fts5(
    href,
    description,
    extended,
    content='bookmarks',
    content_rowid='id'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER bookmarks_fts_insert AFTER INSERT ON bookmarks
BEGIN
    INSERT INTO bookmarks_fts(rowid, href, description, extended)
    VALUES (new.id, new.href, new.description, new.extended);
END;

CREATE TRIGGER bookmarks_fts_update AFTER UPDATE ON bookmarks
BEGIN
    UPDATE bookmarks_fts 
    SET href = new.href,
        description = new.description,
        extended = new.extended
    WHERE rowid = new.id;
END;

CREATE TRIGGER bookmarks_fts_delete AFTER DELETE ON bookmarks
BEGIN
    DELETE FROM bookmarks_fts WHERE rowid = old.id;
END;

-- Update timestamp trigger
CREATE TRIGGER bookmarks_update_timestamp AFTER UPDATE ON bookmarks
BEGIN
    UPDATE bookmarks SET updated_at = CURRENT_TIMESTAMP WHERE id = new.id;
END;

-- View for convenient bookmark querying with tags
CREATE VIEW bookmarks_with_tags AS
SELECT 
    b.id,
    b.href,
    b.description,
    b.extended,
    b.meta,
    b.hash,
    b.time,
    b.shared,
    b.toread,
    b.tags_modified,
    b.sync_status,
    b.last_synced_at,
    b.original_tags,
    b.created_at,
    b.updated_at,
    GROUP_CONCAT(t.name, ' ') as tags
FROM bookmarks b
LEFT JOIN bookmark_tags bt ON b.id = bt.bookmark_id
LEFT JOIN tags t ON bt.tag_id = t.id
GROUP BY b.id;

-- Sync context table to track when sync operations are in progress
CREATE TABLE sync_context (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Triggers to track tag modifications for sync (only when not during sync)
CREATE TRIGGER track_tag_insertions
AFTER INSERT ON bookmark_tags
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM sync_context WHERE key = 'in_sync')
BEGIN
    UPDATE bookmarks 
    SET tags_modified = 1,
        sync_status = 'pending_local'
    WHERE id = NEW.bookmark_id
    AND sync_status = 'synced';
END;

CREATE TRIGGER track_tag_deletions
AFTER DELETE ON bookmark_tags
FOR EACH ROW
WHEN NOT EXISTS (SELECT 1 FROM sync_context WHERE key = 'in_sync')
BEGIN
    UPDATE bookmarks 
    SET tags_modified = 1,
        sync_status = 'pending_local'
    WHERE id = OLD.bookmark_id
    AND sync_status = 'synced';
END;