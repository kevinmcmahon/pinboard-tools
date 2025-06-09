# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed
- Database initialization now loads schema from external `schema.sql` file instead of embedded string
- All exceptions now use proper exception chaining with `from e`
- Improved code formatting to comply with ruff and mypy standards
- **BREAKING**: Replaced generic model classes with strongly-typed dataclasses for `Bookmark`, `Tag`, `BookmarkTag`, and `TagMerge`
- Added TypedDict definitions (`BookmarkRow`, `TagRow`, etc.) for type-safe database query results
- Added helper functions to convert between database rows and dataclass instances

### Security
- SQL queries now use parameter binding instead of string interpolation
- Database connection errors no longer expose internal paths in production

## [0.1.0] - 2024-01-01

### Added
- Initial release
- Database layer with SQLite storage and full-text search
- Bidirectional sync with Pinboard API
- Tag analysis and consolidation features
- Rate-limited API client
- Rich CLI output formatting