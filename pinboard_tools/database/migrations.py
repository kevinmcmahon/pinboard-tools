# ABOUTME: Database migration functions for schema updates
# ABOUTME: Handles adding change tracking and other schema modifications

from .models import Database


def add_change_tracking_columns(db: Database) -> None:
    """Add change tracking columns to existing database"""
    conn = db.connect()

    # Check if columns already exist
    cursor = conn.execute("PRAGMA table_info(bookmarks)")
    columns = {row["name"] for row in cursor}

    if "sync_status" not in columns:
        print("Adding change tracking columns...")

        # Add sync_status column
        conn.execute("""
            ALTER TABLE bookmarks
            ADD COLUMN sync_status TEXT DEFAULT 'synced'
            CHECK (sync_status IN ('synced', 'pending_local', 'pending_remote', 'conflict'))
        """)

        # Add last_synced_at column
        conn.execute("""
            ALTER TABLE bookmarks
            ADD COLUMN last_synced_at TIMESTAMP
        """)

        # Create index for sync_status
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bookmarks_sync_status
            ON bookmarks(sync_status)
        """)

        # Create trigger to update sync_status on changes
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS track_bookmark_changes
            AFTER UPDATE ON bookmarks
            FOR EACH ROW
            WHEN OLD.href != NEW.href
                OR OLD.description != NEW.description
                OR OLD.extended != NEW.extended
                OR OLD.tags != NEW.tags
                OR OLD.toread != NEW.toread
                OR OLD.shared != NEW.shared
            BEGIN
                UPDATE bookmarks
                SET sync_status = 'pending_local',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = NEW.id;
            END;
        """)

        conn.commit()
        print("Change tracking columns added successfully")
    else:
        print("Change tracking columns already exist")


def reset_sync_status(db: Database, status: str = "pending_local") -> None:
    """Reset all sync status to specified value"""
    valid_statuses = ["synced", "pending_local", "pending_remote", "conflict"]
    if status not in valid_statuses:
        raise ValueError(f"Status must be one of: {valid_statuses}")

    conn = db.connect()
    conn.execute("UPDATE bookmarks SET sync_status = ?", (status,))
    conn.commit()

    cursor = conn.execute("SELECT COUNT(*) as count FROM bookmarks")
    count = cursor.fetchone()["count"]
    print(f"Reset {count} bookmarks to status: {status}")


def ensure_schema_current(db: Database) -> None:
    """Ensure database has all required columns and triggers"""
    db.init_schema()
    add_change_tracking_columns(db)
