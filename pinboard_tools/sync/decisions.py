# ABOUTME: Pure sync decision classification for remote-to-local bookmark sync
# ABOUTME: Avoids API and database access so conflict behavior is easy to test

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..utils.datetime import parse_boolean, parse_pinboard_time


class SyncConflictPolicy(Enum):
    NEWEST_WINS = "newest_wins"
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"


class DecisionAction(Enum):
    APPLY_REMOTE = "apply_remote"
    KEEP_LOCAL = "keep_local"
    NOOP = "noop"


@dataclass(frozen=True)
class LocalBookmarkSnapshot:
    href: str
    description: str
    extended: str | None
    shared: bool
    toread: bool
    tags: Sequence[str]
    sync_status: str
    updated_at: datetime | str | None


@dataclass(frozen=True)
class SyncDecision:
    action: DecisionAction


def classify_remote_post(
    *,
    local: LocalBookmarkSnapshot | None,
    remote: Mapping[str, Any],
    conflict_policy: SyncConflictPolicy,
) -> SyncDecision:
    """Classify a remote post against local state without side effects."""
    if local is None:
        return SyncDecision(DecisionAction.APPLY_REMOTE)

    if local.sync_status == "pending_local":
        return SyncDecision(_classify_pending_local(local, remote, conflict_policy))

    if _remote_is_newer(local, remote) or _remote_fields_differ(local, remote):
        return SyncDecision(DecisionAction.APPLY_REMOTE)

    return SyncDecision(DecisionAction.NOOP)


def _classify_pending_local(
    local: LocalBookmarkSnapshot,
    remote: Mapping[str, Any],
    conflict_policy: SyncConflictPolicy,
) -> DecisionAction:
    if conflict_policy == SyncConflictPolicy.LOCAL_WINS:
        return DecisionAction.KEEP_LOCAL
    if conflict_policy == SyncConflictPolicy.REMOTE_WINS:
        return DecisionAction.APPLY_REMOTE

    local_time = _coerce_datetime(local.updated_at)
    remote_time = parse_pinboard_time(str(remote["time"]))
    if local_time is not None and local_time > remote_time:
        return DecisionAction.KEEP_LOCAL
    return DecisionAction.APPLY_REMOTE


def _remote_is_newer(local: LocalBookmarkSnapshot, remote: Mapping[str, Any]) -> bool:
    local_time = _coerce_datetime(local.updated_at)
    if local_time is None:
        return False
    return parse_pinboard_time(str(remote["time"])) > local_time


def _remote_fields_differ(
    local: LocalBookmarkSnapshot, remote: Mapping[str, Any]
) -> bool:
    return (
        remote.get("href") != local.href
        or remote.get("description") != local.description
        or remote.get("extended", "") != (local.extended or "")
        or parse_boolean(remote.get("shared", "yes")) != local.shared
        or parse_boolean(remote.get("toread", "no")) != local.toread
        or _normalize_tags(remote.get("tags", "")) != _normalize_tags(local.tags)
    )


def _coerce_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _normalize_tags(tags: object) -> tuple[str, ...]:
    if tags is None:
        return ()
    if isinstance(tags, str):
        return tuple(sorted(tags.split()))
    if isinstance(tags, Sequence):
        return tuple(sorted(str(tag) for tag in tags))
    return (str(tags),)
