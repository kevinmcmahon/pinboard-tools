# 0006. Idempotent Schema Initialization

## Status

Accepted

## Context

`Database.init_schema()` is the supported entry point for creating and
migrating the SQLite bookmark database. Callers use it before local mirror
upserts, sync operations, search, and tests. Those callers should not need to
know whether a database file is new, empty, partially initialized, or already
at the current schema version.

The bookmark database contains primary local mirror tables plus derived
representations: normalized tag junction rows, the `bookmarks_with_tags` view,
and the `bookmarks_fts` full-text index. Derived objects must be repairable and
rebuildable because local mirror state can lag or be reconciled from Pinboard.

The packaged `schema.sql` previously mixed idempotent table/index creation with
non-idempotent trigger and view creation. Running `init_schema()` against an
existing database could fail with duplicate trigger errors, pushing schema-state
guessing into callers.

## Decision

Keep schema ownership inside pinboard-tools. `Database.init_schema()` and the
packaged `schema.sql` resource must be safe to run repeatedly against an
existing database.

Use `IF NOT EXISTS` for schema objects that are part of the current schema,
including triggers and views. Keep versioned migrations responsible for
replacing objects whose definitions changed. Schema version 3 repairs the FTS
maintenance triggers and rebuilds the FTS index so existing databases converge
with newly initialized databases.

Callers should invoke `Database.init_schema()` before using the local database
instead of inferring schema state from file existence, file size, or private
SQLite internals.

## Consequences

Applications can delegate database creation, migration, and repair to
pinboard-tools without carrying local schema heuristics.

The local SQLite database remains a repairable mirror of Pinboard data. The FTS
index and bookmark/tag views are derived data maintained by schema triggers and
can be rebuilt during migrations when trigger behavior changes.

Future schema changes must preserve mixed-version safety: old databases,
newly-created databases, and databases initialized multiple times should all
converge through `Database.init_schema()`.
