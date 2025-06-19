# Bug Report: Missing schema.sql in pinboard-tools Package

## Summary

The `pinboard-tools` library fails to initialize the database due to a missing `schema.sql` file in the packaged distribution. This is a critical packaging issue that prevents the library from functioning as intended.

## Environment

- **pinboard-tools version**: 0.1.3
- **Python version**: 3.11
- **Installation method**: pip/uv
- **Operating System**: macOS (also affects other platforms)

## Expected Behavior

The `pinboard-tools` library should be self-contained and fully functional after installation. Consumers should be able to use the public API without needing to provide or manage internal database schema files.

```python
from pinboard_tools import init_database, BidirectionalSync

# This should work without any additional setup
init_database("bookmarks.db")
sync = BidirectionalSync(api_token="username:token")
results = sync.sync()
```

## Actual Behavior

The library fails with `FileNotFoundError` when attempting to initialize the database:

```
FileNotFoundError: Schema file not found: /path/to/site-packages/schema.sql
```

## Steps to Reproduce

1. Install pinboard-tools: `pip install pinboard-tools`
2. Try to initialize a database:
   ```python
   from pinboard_tools import init_database
   init_database("test.db")
   ```
3. Error occurs immediately

## Root Cause Analysis

Looking at the source code in `pinboard_tools/database/models.py`, the `init_schema()` method attempts to locate `schema.sql` using:

```python
def init_schema(self) -> None:
    """Initialize database schema from schema.sql file"""
    conn = self.connect()

    # Find schema.sql file relative to this module
    module_dir = Path(__file__).parent.parent.parent
    schema_path = module_dir / "schema.sql"

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
```

This code expects `schema.sql` to be located at the package root level (three directories up from the models.py file), but the file is not included in the distributed package.

## Impact

This is a **critical bug** that makes the library completely unusable. Any application attempting to use pinboard-tools will fail immediately upon trying to initialize the database.

## Proposed Solution

The `schema.sql` file needs to be:

1. **Included in the package distribution** - Ensure the schema file is bundled with the package when built/published
2. **Located correctly** - The file should be in the expected location or the path resolution logic should be updated
3. **Tested in CI/CD** - Add packaging tests to verify all required files are included

### Packaging Fix Options

**Option 1: Include schema.sql in package root**
```
pinboard-tools/
├── schema.sql  # Add this file here
├── pinboard_tools/
│   ├── __init__.py
│   ├── database/
│   └── ...
```

**Option 2: Move schema.sql to a data directory within the package**
```
pinboard-tools/
├── pinboard_tools/
│   ├── __init__.py
│   ├── data/
│   │   └── schema.sql  # Move here
│   ├── database/
│   └── ...
```

Then update the path resolution in `models.py`:
```python
# Option 2 approach
module_dir = Path(__file__).parent.parent
schema_path = module_dir / "data" / "schema.sql"
```

**Option 3: Embed schema as a string constant**
Instead of reading from a file, embed the schema directly in the Python code to eliminate file dependency issues entirely.

## Design Principle Violation

This bug violates a fundamental design principle: **library encapsulation**. Consumer applications should never need to know about or manage internal implementation details like database schemas. The library's public API should abstract away all internal complexity.

A properly encapsulated library should:
- ✅ Provide a clean public API
- ✅ Handle all internal dependencies automatically  
- ✅ Work immediately after installation
- ❌ **Current state**: Exposes internal file dependencies to consumers

## Testing Recommendations

To prevent similar issues:

1. **Package integrity tests**: Verify all required files are included in built packages
2. **Fresh environment tests**: Test library installation and basic usage in clean environments
3. **CI/CD packaging pipeline**: Automated testing of package builds before release

## Workaround

Currently, there is no clean workaround for consumers. The missing schema file makes the library non-functional.

## Additional Context

This issue was discovered while integrating pinboard-tools into a bookmark management application. The expectation was that the library would handle all database operations internally, but the missing schema file prevents any database initialization.

The library's documentation suggests it should work out-of-the-box:

```python
from pinboard_tools import BidirectionalSync, init_database

# Initialize database
init_database("bookmarks.db")

# Create sync client
sync = BidirectionalSync(api_token="your_pinboard_token")
```

However, this code fails immediately due to the packaging issue.

---

**Priority**: Critical - Library is completely non-functional
**Component**: Packaging/Distribution
**Affects**: All users of pinboard-tools library