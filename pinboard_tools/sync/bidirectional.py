# ABOUTME: Bidirectional sync between local database and Pinboard
# ABOUTME: Handles conflicts, incremental updates, and sync strategies

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..database.models import (
    Database,
    get_bookmark_tags_string,
    get_sync_metadata,
    set_sync_metadata,
)
from ..local_mirror import (
    _count_actionable_local_bookmarks,
    _fetch_local_bookmarks_by_hash,
    _fetch_pending_local_bookmarks,
    _mark_bookmark_pending_local,
    _mark_bookmarks_error,
    _mark_bookmarks_synced,
    _retry_error_bookmarks,
    _touch_synced_bookmarks,
    upsert_pinboard_post,
)
from .api import PinboardAPI
from .decisions import (
    DecisionAction,
    LocalBookmarkSnapshot,
    SyncConflictPolicy,
    SyncDecision,
    classify_remote_post,
)


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

    def retry_failed_bookmarks(self) -> int:
        """Reset error'd bookmarks to pending_local so they can be retried on next sync.

        Returns the number of bookmarks reset.
        """
        count = _retry_error_bookmarks(self.db)

        if count > 0:
            print(f"Reset {count} error'd bookmarks to pending_local for retry")

        return count

    def _needs_local_sync(self) -> bool:
        """Check if local changes need to be synced to remote"""
        # Only count actionable statuses, not 'error' (which requires explicit retry)
        local_changes = _count_actionable_local_bookmarks(self.db)
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

    def _mark_bookmarks_synced(self, bookmark_ids: list[int]) -> None:
        """Mark bookmarks as synced in the database"""
        _mark_bookmarks_synced(self.db, bookmark_ids)

    def _mark_bookmarks_error(
        self, bookmarks: list[dict[str, Any]], exclude_ids: list[int]
    ) -> None:
        """Mark bookmarks as error, excluding already-synced ones"""
        _mark_bookmarks_error(self.db, bookmarks, exclude_ids)

    def _sync_local_to_remote(self, dry_run: bool) -> None:
        """Sync local changes to Pinboard"""
        bookmarks = _fetch_pending_local_bookmarks(self.db)

        if dry_run:
            for bookmark in bookmarks:
                print(f"Would sync to remote: {bookmark['href'][:50]}...")
                self.sync_stats["local_to_remote"] += 1
            return

        synced_ids: list[int] = []
        try:
            for bookmark in bookmarks:
                print(f"Syncing to remote: {bookmark['href'][:50]}...")

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
                    synced_ids.append(bookmark["id"])
                    self.sync_stats["local_to_remote"] += 1
                else:
                    print(f"Failed to sync bookmark {bookmark['href']}")
                    _mark_bookmarks_error(self.db, [bookmark], [])
                    self.db.commit()
                    self.sync_stats["errors"] += 1

            self._mark_bookmarks_synced(synced_ids)
            self.db.commit()

        except Exception as e:
            print(f"Error during sync: {e}")
            self._mark_bookmarks_synced(synced_ids)
            self._mark_bookmarks_error(bookmarks, synced_ids)
            self.db.commit()
            self.sync_stats["errors"] += len(bookmarks) - len(synced_ids)
            raise

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
        local_bookmarks = _fetch_local_bookmarks_by_hash(self.db)

        for post in remote_posts:
            hash_value = post["hash"]
            local = local_bookmarks.get(hash_value)
            decision = self._classify_remote_post(local, post, conflict_resolution)

            if local is not None:
                if local["sync_status"] == "pending_local":
                    # Conflict!
                    self._handle_conflict(
                        local, post, conflict_resolution, dry_run, decision.action
                    )
                else:
                    # Check if the remote bookmark has actually changed
                    if decision.action == DecisionAction.APPLY_REMOTE:
                        # Update local with remote changes
                        if not dry_run:
                            upsert_pinboard_post(self.db, post)
                        self.sync_stats["remote_to_local"] += 1
            else:
                # New bookmark from remote
                if not dry_run:
                    upsert_pinboard_post(self.db, post)
                self.sync_stats["remote_to_local"] += 1

    def _handle_conflict(
        self,
        local: dict[str, Any],
        remote: dict[str, Any],
        resolution: ConflictResolution,
        dry_run: bool,
        action: DecisionAction | None = None,
    ) -> None:
        """Handle sync conflicts"""
        self.conflict_count += 1
        print(f"\nConflict detected for: {remote['href'][:50]}")

        if resolution == ConflictResolution.MANUAL:
            # In a real implementation, this would prompt the user
            print("Manual conflict resolution not implemented - using newest wins")
            resolution = ConflictResolution.NEWEST_WINS

        if action is None:
            action = self._classify_remote_post(local, remote, resolution).action

        if action == DecisionAction.KEEP_LOCAL:
            print("  -> Keeping local version")
            # Mark for upload to remote
            if not dry_run:
                _mark_bookmark_pending_local(self.db, local["id"])
        elif action == DecisionAction.APPLY_REMOTE:
            print("  -> Using remote version")
            if not dry_run:
                upsert_pinboard_post(self.db, remote)

        self.sync_stats["conflicts_resolved"] += 1

    def _bookmark_needs_update(
        self, local: dict[str, Any], remote: dict[str, Any]
    ) -> bool:
        """Check if a remote bookmark has changes that need to be applied locally"""
        return bool(
            self._classify_remote_post(
                local, remote, ConflictResolution.REMOTE_WINS
            ).action
            == DecisionAction.APPLY_REMOTE
        )

    def _classify_remote_post(
        self,
        local: dict[str, Any] | None,
        remote: dict[str, Any],
        conflict_resolution: ConflictResolution,
    ) -> SyncDecision:
        return classify_remote_post(
            local=self._snapshot_local_bookmark(local) if local is not None else None,
            remote=remote,
            conflict_policy=_to_decision_policy(conflict_resolution),
        )

    def _snapshot_local_bookmark(self, local: dict[str, Any]) -> LocalBookmarkSnapshot:
        return LocalBookmarkSnapshot(
            href=local["href"],
            description=local["description"],
            extended=local.get("extended"),
            shared=bool(local.get("shared", True)),
            toread=bool(local.get("toread", False)),
            tags=get_bookmark_tags_string(self.db, local["id"]).split(),
            sync_status=local.get("sync_status", "synced"),
            updated_at=local.get("updated_at"),
        )

    def _update_sync_timestamps(self) -> None:
        """Update last sync timestamp for all synced bookmarks and sync metadata"""
        now = datetime.now(UTC)
        _touch_synced_bookmarks(self.db, now)

        # Update sync metadata to record successful remote sync
        if self.sync_stats["remote_to_local"] > 0:
            set_sync_metadata(self.db, "last_remote_sync", now)

        self.db.commit()


def _to_decision_policy(resolution: ConflictResolution) -> SyncConflictPolicy:
    if resolution == ConflictResolution.LOCAL_WINS:
        return SyncConflictPolicy.LOCAL_WINS
    if resolution == ConflictResolution.REMOTE_WINS:
        return SyncConflictPolicy.REMOTE_WINS
    return SyncConflictPolicy.NEWEST_WINS
