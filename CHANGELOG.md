# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2025-06-19

### Added
- Enhanced tag architecture with comprehensive normalized storage system
- New `TagManager` class for centralized tag operations and validation
- Tag normalization utilities with whitespace handling and duplicate detection
- Comprehensive tag consolidation workflow with preview and confirmation
- Advanced tag similarity detection using multiple algorithms (exact match, fuzzy matching, semantic similarity)
- Rich CLI output with colored formatting and structured tables
- Tag analytics and reporting features
- Batch tag operations with optimized database queries

### Changed
- **BREAKING**: Upgraded database schema to fully normalized tag storage with junction tables
- Refactored tag operations to use centralized `TagManager` instead of scattered methods
- Improved tag similarity algorithms with configurable thresholds
- Enhanced CLI with better user experience and visual feedback
- Optimized database queries for tag operations to reduce N+1 patterns

### Performance
- Significantly improved tag consolidation performance through batch operations
- Reduced database queries for tag similarity detection
- Optimized tag normalization with caching for repeated operations

## [0.1.4] - 2025-06-19

### Fixed
- **CRITICAL**: Fixed missing schema.sql file in package distribution that made the library completely non-functional after installation
- Schema file is now properly included as package data using `importlib.resources` for reliable access in both development and installed environments
- Updated schema loading to use modern `importlib.resources.files()` API instead of deprecated `read_text()`

### Added
- Comprehensive packaging tests to prevent future distribution issues
- Package integrity tests that simulate real-world installation scenarios
- Added `/pinboard_tools/data/` directory containing `schema.sql` as package data

### Changed
- Moved schema.sql from project root to `pinboard_tools/data/schema.sql` for proper packaging
- Database initialization now uses `importlib.resources` instead of file path resolution
- Improved error messages to clearly indicate package data access issues

## [0.1.2] - 2025-06-10

### Added
- Release automation with GitHub Actions workflow for PyPI publishing
- Comprehensive release documentation (RELEASING.md)
- py.typed marker for proper type checker support

### Changed
- Improved CI/CD pipeline with automated version tagging and changelog validation

## [0.1.1] - 2025-06-10

### Fixed
- **CRITICAL**: Fixed schema inconsistency between `schema.sql` and `models.py` - database now uses single source of truth from `schema.sql` file
- **SECURITY**: Fixed SQL injection vulnerability in `get_unread_bookmarks()` function - now uses parameterized queries
- Added proper error handling for database connection failures with descriptive error messages
- Added comprehensive error handling in API client for network errors (ConnectionError, Timeout, RequestException)
- Fixed test compatibility issues with case-insensitive tag collation

### Added
- Custom `PinboardAPIError` exception class for better error handling
- Foreign key constraints are now properly enabled on database connections
- Added constants for API rate limiting (`PINBOARD_RATE_LIMIT_SECONDS`, `RATE_LIMIT_BUFFER`)
- Added test for batch tag operations to verify N+1 query optimization
- Comprehensive Sphinx documentation with API reference, user guides, and examples
- RTD theme with autodoc, type hints, and intersphinx support

### Changed
- Database initialization now loads schema from external `schema.sql` file instead of embedded string
- All exceptions now use proper exception chaining with `from e`
- Improved code formatting to comply with ruff and mypy standards
- Replaced generic model classes with strongly-typed dataclasses for `Bookmark`, `Tag`, `BookmarkTag`, and `TagMerge`
- Added TypedDict definitions (`BookmarkRow`, `TagRow`, etc.) for type-safe database query results
- Added helper functions to convert between database rows and dataclass instances
- Removed non-idiomatic datetime utility aliases (`parse_datetime`, `format_datetime`) - use explicit `parse_pinboard_time` and `format_pinboard_time` instead

### Performance
- **MAJOR**: Optimized N+1 query pattern in `_update_bookmark_tags()` method - now uses batch operations instead of individual queries for each tag
  - Reduced database round trips from O(N) to O(1) for tag updates where N = number of tags
  - Uses `executemany()` for batch inserts and single `IN` clause query to fetch tag IDs
  - Significantly improves sync performance for bookmarks with many tags

### Security
- SQL queries now use parameter binding instead of string interpolation
- Database connection errors no longer expose internal paths in production

## [0.1.0] - 2025-06-09

### Added
- Initial release
- Database layer with SQLite storage and full-text search
- Bidirectional sync with Pinboard API
- Tag analysis and consolidation features
- Rate-limited API client
- Rich CLI output formatting
