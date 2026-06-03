# ABOUTME: Pure tests for sync decision classification
# ABOUTME: Verifies remote/local sync actions without API or database access

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pinboard_tools.sync.decisions import (
    DecisionAction,
    LocalBookmarkSnapshot,
    SyncConflictPolicy,
    classify_remote_post,
)


def _remote_post(**overrides: object) -> dict[str, object]:
    post: dict[str, object] = {
        "hash": "hash1",
        "href": "https://example.com/1",
        "description": "Bookmark",
        "extended": "Notes",
        "tags": "python testing",
        "time": "2024-01-01T12:00:00Z",
        "shared": "yes",
        "toread": "no",
    }
    post.update(overrides)
    return post


def _local_snapshot(**overrides: object) -> LocalBookmarkSnapshot:
    snapshot = LocalBookmarkSnapshot(
        href="https://example.com/1",
        description="Bookmark",
        extended="Notes",
        shared=True,
        toread=False,
        tags=("testing", "python"),
        sync_status="synced",
        updated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    return replace(snapshot, **overrides)


def test_no_local_bookmark_applies_remote() -> None:
    decision = classify_remote_post(
        local=None,
        remote=_remote_post(),
        conflict_policy=SyncConflictPolicy.NEWEST_WINS,
    )

    assert decision.action is DecisionAction.APPLY_REMOTE


def test_identical_synced_bookmark_with_different_tag_order_is_noop() -> None:
    decision = classify_remote_post(
        local=_local_snapshot(tags=("testing", "python")),
        remote=_remote_post(tags="python testing"),
        conflict_policy=SyncConflictPolicy.NEWEST_WINS,
    )

    assert decision.action is DecisionAction.NOOP


def test_changed_remote_fields_apply_remote() -> None:
    remote_overrides = [
        {"href": "https://example.com/moved"},
        {"description": "Changed title"},
        {"extended": "Changed notes"},
        {"shared": "no"},
        {"toread": "yes"},
        {"tags": "python testing changed"},
    ]

    for override in remote_overrides:
        decision = classify_remote_post(
            local=_local_snapshot(),
            remote=_remote_post(**override),
            conflict_policy=SyncConflictPolicy.NEWEST_WINS,
        )
        assert decision.action is DecisionAction.APPLY_REMOTE


def test_newer_remote_timestamp_applies_remote() -> None:
    decision = classify_remote_post(
        local=_local_snapshot(
            updated_at=datetime(2024, 1, 1, 11, 59, 0, tzinfo=UTC),
        ),
        remote=_remote_post(time="2024-01-01T12:00:00Z"),
        conflict_policy=SyncConflictPolicy.NEWEST_WINS,
    )

    assert decision.action is DecisionAction.APPLY_REMOTE


def test_pending_local_with_local_wins_keeps_local() -> None:
    decision = classify_remote_post(
        local=_local_snapshot(sync_status="pending_local"),
        remote=_remote_post(description="Remote conflict"),
        conflict_policy=SyncConflictPolicy.LOCAL_WINS,
    )

    assert decision.action is DecisionAction.KEEP_LOCAL


def test_pending_local_with_remote_wins_applies_remote() -> None:
    decision = classify_remote_post(
        local=_local_snapshot(sync_status="pending_local"),
        remote=_remote_post(description="Remote conflict"),
        conflict_policy=SyncConflictPolicy.REMOTE_WINS,
    )

    assert decision.action is DecisionAction.APPLY_REMOTE


def test_pending_local_newest_wins_keeps_newer_local() -> None:
    remote_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    decision = classify_remote_post(
        local=_local_snapshot(
            sync_status="pending_local",
            updated_at=remote_time + timedelta(minutes=1),
        ),
        remote=_remote_post(time=remote_time.isoformat()),
        conflict_policy=SyncConflictPolicy.NEWEST_WINS,
    )

    assert decision.action is DecisionAction.KEEP_LOCAL


def test_pending_local_newest_wins_applies_newer_remote() -> None:
    remote_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
    decision = classify_remote_post(
        local=_local_snapshot(
            sync_status="pending_local",
            updated_at=remote_time - timedelta(minutes=1),
        ),
        remote=_remote_post(time=remote_time.isoformat()),
        conflict_policy=SyncConflictPolicy.NEWEST_WINS,
    )

    assert decision.action is DecisionAction.APPLY_REMOTE


def test_naive_local_updated_at_compares_safely_with_utc_remote_time() -> None:
    decision = classify_remote_post(
        local=_local_snapshot(
            sync_status="pending_local",
            updated_at=datetime(2024, 1, 1, 12, 1, 0),
        ),
        remote=_remote_post(time="2024-01-01T12:00:00Z"),
        conflict_policy=SyncConflictPolicy.NEWEST_WINS,
    )

    assert decision.action is DecisionAction.KEEP_LOCAL


def test_remote_wins_policy_does_not_apply_identical_synced_bookmark() -> None:
    decision = classify_remote_post(
        local=_local_snapshot(sync_status="synced"),
        remote=_remote_post(),
        conflict_policy=SyncConflictPolicy.REMOTE_WINS,
    )

    assert decision.action is DecisionAction.NOOP
