# ABOUTME: Bidirectional sync between local database and Pinboard
# ABOUTME: Handles conflicts, incremental updates, and sync strategies

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..database.models import (
    Database,
    get_bookmark_tags_string,
    get_sync_metadata,
    set_bookmark_tags,
    set_sync_metadata,
)
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
        # Reset sync stats for this operation
        self.sync_stats = {
            "local_to_remote": 0,
            "remote_to_local": 0,
            "conflicts_resolved": 0,
            "errors": 0,
        }

        print(
            f"Starting sync - Direction: {direction.value}, Conflict Resolution: {conflict_resolution.value}"
        )

        # Check what needs syncing
        needs_local_sync = False
        needs_remote_sync = False

        if direction in [SyncDirection.BIDIRECTIONAL, SyncDirection.LOCAL_TO_REMOTE]:
            needs_local_sync = self._needs_local_sync()

        if direction in [SyncDirection.BIDIRECTIONAL, SyncDirection.REMOTE_TO_LOCAL]:
            needs_remote_sync = self._needs_remote_sync()

        if not needs_local_sync and not needs_remote_sync:
            print("No changes to sync")
            return self.sync_stats

        if needs_local_sync:
            self._sync_local_to_remote(dry_run)

        if needs_remote_sync:
            self._sync_remote_to_local(conflict_resolution, dry_run)

        # Update sync timestamps
        if not dry_run:
            self._update_sync_timestamps()

        print(f"\nSync complete: {self.sync_stats}")
        return self.sync_stats

    def _needs_local_sync(self) -> bool:
        """Check if local changes need to be synced to remote"""
        cursor = self.db.execute(
            "SELECT COUNT(*) as count FROM bookmarks WHERE sync_status != 'synced'"
        )
        local_changes = cursor.fetchone()["count"]
        if local_changes > 0:
            print(f"Found {local_changes} local changes to sync")
            return True
        return False

    def _needs_remote_sync(self) -> bool:
        """Check if remote changes need to be synced to local"""
        # Get last successful remote sync from sync metadata
        last_sync_dt = get_sync_metadata(self.db, "last_remote_sync")

        if last_sync_dt:
            last_update = self.api.get_last_update()
            if last_update > last_sync_dt:
                print(
                    f"Remote changes detected (last update: {last_update.isoformat()}, last sync: {last_sync_dt.isoformat()})"
                )
                return True
            else:
                print(f"No remote changes since last sync ({last_sync_dt.isoformat()})")
                return False
        else:
            print("No previous sync detected - performing initial sync")
            return True

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
        # Get last sync time from sync metadata to fetch only changed posts
        last_sync_dt = get_sync_metadata(self.db, "last_remote_sync")

        if last_sync_dt:
            print(f"Fetching posts changed since {last_sync_dt.isoformat()}...")
            remote_posts = self.api.get_all_posts(fromdt=last_sync_dt)
        else:
            print("Fetching all posts from Pinboard (initial sync)...")
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
                        # Check if the remote bookmark has actually changed
                        if self._bookmark_needs_update(local, post):
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

    def _bookmark_needs_update(
        self, local: dict[str, Any], remote: dict[str, Any]
    ) -> bool:
        """Check if a remote bookmark has changes that need to be applied locally"""
        # Compare key fields to see if they differ
        remote_time = parse_pinboard_time(remote["time"])
        local_time = None
        if local.get("updated_at"):
            local_time = datetime.fromisoformat(local["updated_at"])
            # Ensure both datetimes have timezone info for comparison
            if local_time.tzinfo is None:
                local_time = local_time.replace(tzinfo=UTC)

        # If remote is newer, it needs updating
        if local_time and remote_time > local_time:
            return True

        # Check if basic fields differ
        if (
            remote.get("href") != local.get("href")
            or remote.get("description") != local.get("description")
            or remote.get("extended", "") != local.get("extended", "")
            or parse_boolean(remote.get("shared", "yes"))
            != bool(local.get("shared", True))
            or parse_boolean(remote.get("toread", "no"))
            != bool(local.get("toread", False))
        ):
            return True

        # Get local tags and compare with remote tags
        local_tags = get_bookmark_tags_string(self.db, local["id"])
        remote_tags = remote.get("tags", "")

        # Normalize tag strings for comparison (split, sort, rejoin)
        local_tags_normalized = " ".join(sorted(local_tags.split()))
        remote_tags_normalized = " ".join(sorted(remote_tags.split()))

        return local_tags_normalized != remote_tags_normalized

    def _update_sync_timestamps(self) -> None:
        """Update last sync timestamp for all synced bookmarks and sync metadata"""
        now = datetime.now(UTC)
        now_iso = now.isoformat()

        self.db.execute(
            "UPDATE bookmarks SET last_synced_at = ? WHERE sync_status = 'synced'",
            (now_iso,),
        )

        # Update sync metadata to record successful remote sync
        if self.sync_stats["remote_to_local"] > 0:
            set_sync_metadata(self.db, "last_remote_sync", now)

        self.db.commit()
