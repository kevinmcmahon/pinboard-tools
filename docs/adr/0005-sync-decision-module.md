# 0005. Sync Decision Module

## Status

Accepted

## Context

Remote-to-local bidirectional sync needs to decide whether a Pinboard post
should update the local bookmark, be ignored, or lose to a pending local
change. Before this decision, that classification logic lived inside
`BidirectionalSync` next to API calls, database lookups, local mirror writes,
conflict counters, dry-run handling, and status updates.

Keeping classification and orchestration together made conflict behavior harder
to test directly. It also meant timestamp and tag comparison rules were tied to
database access even though the decision only needs a local snapshot, a remote
post, and a conflict policy.

## Decision

Add `pinboard_tools.sync.decisions` as a pure sync decision module. It accepts a
`LocalBookmarkSnapshot`, a Pinboard-shaped remote post, and a local conflict
policy enum, then returns a small action enum.

The decision module does not call the Pinboard API, read or write the database,
or import `BidirectionalSync`'s public conflict enum. `BidirectionalSync`
remains the orchestrator: it fetches remote posts, builds local snapshots,
translates its existing `ConflictResolution` values into decision policies,
applies local mirror writes, preserves dry-run behavior, and updates sync
statistics.

## Consequences

Sync classification rules are directly testable without API or SQLite setup.
The rules for tag-order-insensitive equality, remote field changes, newer
remote timestamps, pending local conflicts, and naive local timestamp
comparison live in one focused module.

`BidirectionalSync` keeps its public behavior and enum surface while delegating
classification. Future changes to sync policy can be tested in the pure module
before changing orchestration or persistence code.
