# 0001. Local Bookmark Upsert Public API

## Status

Accepted

## Context

Applications that write directly to Pinboard may also need to keep the local
pinboard-tools SQLite database current. Before this decision, the code that
inserted or updated local bookmarks from remote Pinboard posts lived inside the
private `BidirectionalSync` implementation. Callers outside pinboard-tools had
to either run a broader sync or duplicate schema-specific SQL and tag handling.

## Decision

Expose `upsert_pinboard_post(db, post)` as the public local mirror API. The
function accepts a Pinboard-shaped post, validates the required fields, inserts
or updates the local bookmark, updates normalized tags, marks the bookmark
`synced`, and records `last_synced_at`.

Invalid post data raises `InvalidPinboardPostError`.

## Consequences

Write-through clients can save remotely and mirror the saved remote post
locally without depending on private sync methods. The local database remains
consistent with the same normalized tag tables used by sync.

Callers are still responsible for obtaining a fresh Pinboard-shaped post from
the API after a remote write, so the mirrored row uses Pinboard's authoritative
`hash`, `time`, and metadata.
