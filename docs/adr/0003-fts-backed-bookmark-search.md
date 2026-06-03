# 0003. FTS-Backed Bookmark Search

## Status

Accepted

## Context

The documentation advertises full-text search support for bookmarks, and the
packaged SQLite schema already creates a `bookmarks_fts` FTS5 virtual table over
bookmark `href`, `description`, and `extended` content. Schema triggers keep the
FTS table synchronized with the canonical `bookmarks` rows.

The supported database query surface includes bookmark search. That helper
should match the documented architecture and the schema that already exists:
search should use the FTS index rather than scanning bookmark columns with
`LIKE` predicates.

Bookmark search also accepts raw user input. SQLite FTS query syntax is more
expressive than plain text search, so treating user input as an FTS expression
directly can change search meaning or raise syntax errors. Search results still
need to be returned as bookmark-shaped rows that include normalized tags.

## Decision

Use `bookmarks_fts` as the backing index for the bookmark search query helper.
The helper should join FTS matches back to `bookmarks_with_tags` so callers
continue to receive bookmark rows with tag strings, not FTS-only rows.

Schema version 3 repairs the external-content FTS maintenance triggers and
rebuilds `bookmarks_fts` for existing databases so current installs get the
same update and delete behavior as newly initialized databases.

Raw user input must be handled as data. The helper should bind values through
SQLite parameters and transform user text into a safe FTS query form before
using `MATCH`; it should not concatenate raw input into SQL or treat raw input
as trusted FTS syntax.

## Consequences

Bookmark search behavior aligns with the documented full-text search feature
and uses the schema's maintained FTS5 index instead of column-wide `LIKE`
scans.

Search callers keep the same result shape, including tags from the normalized
tag model, while the implementation can rely on SQLite FTS ranking and matching
semantics in the future.

User-entered punctuation, operators, or malformed FTS syntax should not be able
to break the query or alter the SQL statement. The helper is responsible for
normalizing that input into supported FTS search terms.
