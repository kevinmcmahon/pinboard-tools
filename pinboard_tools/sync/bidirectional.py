# ABOUTME: Bidirectional sync between local database and Pinboard
# ABOUTME: Handles conflicts, incremental updates, and sync strategies

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..database.models import Database, get_bookmark_tags_string, set_bookmark_tags
from ..utils.datetime import parse_boolean, parse_pinboard_time
from .api import PinboardAPI


class SyncDirection(Enum):
    BIDIRECTIONAL = "bidirectional"
    LOCAL_TO_REMOTE = "local_to_remote"
    REMOTE_TO_LOCAL = "remote_to_local"


class ConflictResolution(Enum):
    NEWEST_WINS = "newest_wins"
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    MANUAL = "manual"


class BidirectionalSync:
    """Handles bidirectional sync between local database and Pinboard"""

    def __init__(self, db: Database, api_token: str):
        self.db = db
        self.api = PinboardAPI(api_token)
        self.conflict_count = 0
        self.sync_stats = {
            "local_to_remote": 0,
            "remote_to_local": 0,
            "conflicts_resolved": 0,
            "errors": 0,
        }

    def sync(
        self,
        direction: SyncDirection = SyncDirection.BIDIRECTIONAL,
        conflict_resolution: ConflictResolution = ConflictResolution.NEWEST_WINS,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Perform sync operation"""
        print(
            f"Starting sync - Direction: {direction.value}, Conflict Resolution: {conflict_resolution.value}"
        )

        # Check if we need to sync
        if not self._needs_sync(direction):
            print("No changes to sync")
            return self.sync_stats

        if direction in [SyncDirection.BIDIRECTIONAL, SyncDirection.LOCAL_TO_REMOTE]:
            self._sync_local_to_remote(dry_run)

        if direction in [SyncDirection.BIDIRECTIONAL, SyncDirection.REMOTE_TO_LOCAL]:
            self._sync_remote_to_local(conflict_resolution, dry_run)

        # Update sync timestamps
        if not dry_run:
            self._update_sync_timestamps()

        print(f"\nSync complete: {self.sync_stats}")
        return self.sync_stats

    def _needs_sync(self, direction: SyncDirection) -> bool:
        """Check if sync is needed"""
        # Check for local changes
        if direction in [SyncDirection.BIDIRECTIONAL, SyncDirection.LOCAL_TO_REMOTE]:
            cursor = self.db.execute(
                "SELECT COUNT(*) as count FROM bookmarks WHERE sync_status != 'synced'"
            )
            if cursor.fetchone()["count"] > 0:
                return True

        # Check for remote changes
        if direction in [SyncDirection.BIDIRECTIONAL, SyncDirection.REMOTE_TO_LOCAL]:
            cursor = self.db.execute(
                "SELECT MAX(last_synced_at) as last_sync FROM bookmarks"
            )
            last_sync = cursor.fetchone()["last_sync"]

            if last_sync:
                last_sync_dt = datetime.fromisoformat(last_sync)
                last_update = self.api.get_last_update()
                if last_update > last_sync_dt:
                    return True
            else:
                return True  # No sync timestamp means we need initial sync

        return False

    def _sync_local_to_remote(self, dry_run: bool) -> None:
        """Sync local changes to Pinboard"""
        cursor = self.db.execute(
            "SELECT * FROM bookmarks WHERE sync_status = 'pending_local'"
        )

        for row in cursor:
            bookmark = dict(row)
            print(f"Syncing to remote: {bookmark['href'][:50]}...")

            if not dry_run:
                try:
                    # Get tags from normalized tables
                    tags_string = get_bookmark_tags_string(self.db, bookmark["id"])

                    success = self.api.add_post(
                        url=bookmark["href"],
                        description=bookmark["description"],
                        extended=bookmark["extended"] or "",
                        tags=tags_string,
                        dt=datetime.fromisoformat(bookmark["time"]),
                        shared="yes" if bookmark["shared"] else "no",
                        toread="yes" if bookmark["toread"] else "no",
                    )

                    if success:
                        self.db.execute(
                            "UPDATE bookmarks SET sync_status = 'synced', last_synced_at = ? WHERE id = ?",
                            (datetime.now(UTC).isoformat(), bookmark["id"]),
                        )
                        self.sync_stats["local_to_remote"] += 1
                    else:
                        self.sync_stats["errors"] += 1
                except Exception as e:
                    print(f"Error syncing {bookmark['href']}: {e}")
                    self.sync_stats["errors"] += 1
            else:
                self.sync_stats["local_to_remote"] += 1

    def _sync_remote_to_local(
        self, conflict_resolution: ConflictResolution, dry_run: bool
    ) -> None:
        """Sync remote changes to local database"""
        # Get all posts from Pinboard
        print("Fetching all posts from Pinboard...")
        remote_posts = self.api.get_all_posts()

        # Build lookup of local bookmarks by hash
        cursor = self.db.execute(
            "SELECT hash, id, updated_at, sync_status FROM bookmarks"
        )
        local_bookmarks = {row["hash"]: dict(row) for row in cursor}

        # Enter sync context to prevent triggers from marking bookmarks as pending
        if not dry_run:
            self.db.enter_sync_context()

        try:
            for post in remote_posts:
                hash_value = post["hash"]

                if hash_value in local_bookmarks:
                    # Check if we need to update
                    local = local_bookmarks[hash_value]
                    if local["sync_status"] == "pending_local":
                        # Conflict!
                        self._handle_conflict(local, post, conflict_resolution, dry_run)
                    else:
                        # Update local with remote changes
                        if not dry_run:
                            self._update_bookmark_from_remote(post)
                        self.sync_stats["remote_to_local"] += 1
                else:
                    # New bookmark from remote
                    if not dry_run:
                        self._insert_bookmark_from_remote(post)
                    self.sync_stats["remote_to_local"] += 1
        finally:
            # Always exit sync context
            if not dry_run:
                self.db.exit_sync_context()

    def _handle_conflict(
        self,
        local: dict[str, Any],
        remote: dict[str, Any],
        resolution: ConflictResolution,
        dry_run: bool,
    ) -> None:
        """Handle sync conflicts"""
        self.conflict_count += 1
        print(f"\nConflict detected for: {remote['href'][:50]}")

        if resolution == ConflictResolution.MANUAL:
            # In a real implementation, this would prompt the user
            print("Manual conflict resolution not implemented - using newest wins")
            resolution = ConflictResolution.NEWEST_WINS

        if resolution == ConflictResolution.LOCAL_WINS:
            print("  -> Keeping local version")
            # Mark for upload to remote
            if not dry_run:
                self.db.execute(
                    "UPDATE bookmarks SET sync_status = 'pending_local' WHERE id = ?",
                    (local["id"],),
                )
        elif resolution == ConflictResolution.REMOTE_WINS:
            print("  -> Using remote version")
            if not dry_run:
                self._update_bookmark_from_remote(remote)
        elif resolution == ConflictResolution.NEWEST_WINS:
            # Compare timestamps
            local_time = datetime.fromisoformat(local["updated_at"])
            remote_time = parse_pinboard_time(remote["time"])

            if local_time > remote_time:
                print(f"  -> Local is newer ({local_time} > {remote_time})")
                if not dry_run:
                    self.db.execute(
                        "UPDATE bookmarks SET sync_status = 'pending_local' WHERE id = ?",
                        (local["id"],),
                    )
            else:
                print(f"  -> Remote is newer ({remote_time} > {local_time})")
                if not dry_run:
                    self._update_bookmark_from_remote(remote)

        self.sync_stats["conflicts_resolved"] += 1

    def _update_bookmark_from_remote(self, post: dict[str, Any]) -> None:
        """Update local bookmark with remote data"""
        self.db.execute(
            """
            UPDATE bookmarks
            SET href = ?, description = ?, extended = ?,
                time = ?, toread = ?, shared = ?, meta = ?,
                sync_status = 'synced', last_synced_at = ?
            WHERE hash = ?
        """,
            (
                post["href"],
                post["description"],
                post.get("extended", ""),
                post["time"],
                parse_boolean(post.get("toread", "no")),
                parse_boolean(post.get("shared", "yes")),
                post.get("meta", ""),
                datetime.now(UTC).isoformat(),
                post["hash"],
            ),
        )

        # Update tags using normalized approach
        self._update_bookmark_tags(post["hash"], post.get("tags", ""))

    def _insert_bookmark_from_remote(self, post: dict[str, Any]) -> None:
        """Insert new bookmark from remote"""
        self.db.execute(
            """
            INSERT INTO bookmarks (hash, href, description, extended, meta, time, toread, shared, sync_status, last_synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'synced', ?)
        """,
            (
                post["hash"],
                post["href"],
                post["description"],
                post.get("extended", ""),
                post.get("meta", ""),
                post["time"],
                parse_boolean(post.get("toread", "no")),
                parse_boolean(post.get("shared", "yes")),
                datetime.now(UTC).isoformat(),
            ),
        )

        # Update tags using normalized approach
        self._update_bookmark_tags(post["hash"], post.get("tags", ""))

    def _update_bookmark_tags(self, bookmark_hash: str, tags_str: str) -> None:
        """Update bookmark tags in normalized tables"""
        # Get bookmark ID
        cursor = self.db.execute(
            "SELECT id FROM bookmarks WHERE hash = ?", (bookmark_hash,)
        )
        row = cursor.fetchone()
        if not row:
            return

        bookmark_id = row["id"]

        # Parse tags from string
        tags = [tag.strip() for tag in tags_str.split()] if tags_str else []

        # Use utility function to set tags
        set_bookmark_tags(self.db, bookmark_id, tags)

    def _update_sync_timestamps(self) -> None:
        """Update last sync timestamp for all synced bookmarks"""
        now = datetime.now(UTC).isoformat()
        self.db.execute(
            "UPDATE bookmarks SET last_synced_at = ? WHERE sync_status = 'synced'",
            (now,),
        )
        self.db.commit()
