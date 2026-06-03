# 0002. Retire Obsolete Database Surface

## Status

Accepted

## Context

The database package has accumulated obsolete standalone schema migration
helpers and row conversion helpers that are no longer part of the supported
database surface. The active schema initialization path is
`Database.init_schema()`, which loads the packaged `schema.sql` resource.

Some database types and helpers remain current and useful: dataclasses,
row-shaped type definitions, tag helpers, query helpers, `BookmarkTag`, and
`TagMerge` are still part of the documented surface where applicable.

## Decision

Retire only the stale database migration helpers and unused row conversion
helpers from documentation and release notes.

Keep documenting the current bookmark row converter, the database dataclasses,
row-shaped type definitions, normalized tag helpers, and query helpers. Schema
ownership remains with `Database.init_schema()` and packaged
`schema.sql`.

## Consequences

The public documentation no longer advertises helper APIs that callers should
not depend on.

Existing supported database models, tag operations, query helpers, and packaged
schema initialization remain visible and unchanged.
