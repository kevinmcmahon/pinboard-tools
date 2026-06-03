# 0004. Local Mirror Persistence Seam

## Status

Accepted

## Context

`upsert_pinboard_post(db, post)` is the public local mirror API for writing a
Pinboard-shaped post into the SQLite bookmark store. Bidirectional sync also
needs several bookmark persistence operations: finding pending local bookmarks,
building local bookmark lookups, marking sync success or error, retrying failed
bookmarks, and touching synced rows after a successful sync.

Before this decision, those SQL statements were mixed into
`BidirectionalSync`. That made the sync workflow responsible for both
orchestration and bookmark persistence details, even when the SQL operated on
the same local mirror state used by the public upsert helper.

## Decision

Keep `upsert_pinboard_post(db, post)` as the only documented local mirror
entry point, and keep `InvalidPinboardPostError` unchanged.

Move focused bookmark persistence SQL into private helpers in
`pinboard_tools.local_mirror`. `BidirectionalSync` delegates local bookmark
queries and sync-status updates to those helpers while keeping its existing
transaction boundaries. The retry helper commits because the existing
`retry_failed_bookmarks()` behavior commits the reset immediately.

Do not introduce a broad repository class. The current need is a narrow
persistence seam around local mirror bookmark operations, not a new object model
or abstraction for every database query.

## Consequences

Bookmark persistence logic used by local mirror and bidirectional sync is easier
to test directly and easier to keep consistent.

`BidirectionalSync` remains the sync orchestrator and conflict-resolution owner,
while `local_mirror` owns focused bookmark persistence details.

The private helper names are implementation details. Callers should continue to
use the documented public API rather than depending on these helpers.
