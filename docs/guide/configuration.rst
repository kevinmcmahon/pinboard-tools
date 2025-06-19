=============
Configuration
=============

Database Setup
==============

Initialize Database
-------------------

Before using the library, you need to initialize the SQLite database:

.. code-block:: python

   from pinboard_tools import init_database

   # Initialize with default location
   init_database()

   # Or specify a custom path
   init_database("/path/to/your/bookmarks.db")

Database Schema
---------------

The database uses a normalized schema with the following tables:

- ``bookmarks``: Main bookmark storage
- ``tags``: Normalized tag storage
- ``bookmark_tags``: Many-to-many relationship table
- ``bookmarks_fts``: Full-text search virtual table

API Authentication
==================

Pinboard API Token
------------------

You'll need a Pinboard API token to sync with Pinboard.in:

1. Log in to your Pinboard account
2. Go to Settings → Password
3. Copy your API token (format: ``username:TOKEN``)

.. code-block:: python

   from pinboard_tools import BidirectionalSync, get_session, init_database
   
   # Initialize database first
   init_database()
   db = get_session()

   # Initialize sync client
   sync = BidirectionalSync(db=db, api_token="your_username:your_token")

Environment Variables
---------------------

You can also set the token via environment variable:

.. code-block:: bash

   export PINBOARD_API_TOKEN="your_username:your_token"

.. code-block:: python

   import os
   from pinboard_tools import BidirectionalSync, get_session, init_database

   # Initialize database
   init_database()
   db = get_session()
   
   token = os.getenv("PINBOARD_API_TOKEN")
   sync = BidirectionalSync(db=db, api_token=token)

Rate Limiting
=============

The library automatically handles Pinboard's rate limiting requirements:

- Minimum 3 seconds between API requests
- Automatic retry on rate limit errors (429)
- Configurable rate limit buffer

.. code-block:: python

   from pinboard_tools.sync.api import PINBOARD_RATE_LIMIT_SECONDS
   
   print(f"Rate limit: {PINBOARD_RATE_LIMIT_SECONDS} seconds between requests")

Sync Configuration
==================

Sync Direction
--------------

Configure which direction to sync:

.. code-block:: python

   from pinboard_tools import BidirectionalSync, get_session, init_database
   from pinboard_tools.sync.bidirectional import SyncDirection

   # Initialize database
   init_database()
   db = get_session()
   sync = BidirectionalSync(db=db, api_token="your_token")

   # Bidirectional sync (default)
   sync.sync(direction=SyncDirection.BIDIRECTIONAL)

   # Only sync local changes to remote
   sync.sync(direction=SyncDirection.LOCAL_TO_REMOTE)

   # Only sync remote changes to local
   sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

Conflict Resolution
-------------------

Configure how to handle conflicts:

.. code-block:: python

   from pinboard_tools.sync.bidirectional import ConflictResolution

   # Newest timestamp wins (default)
   sync.sync(conflict_resolution=ConflictResolution.NEWEST_WINS)

   # Always use local version
   sync.sync(conflict_resolution=ConflictResolution.LOCAL_WINS)

   # Always use remote version
   sync.sync(conflict_resolution=ConflictResolution.REMOTE_WINS)

   # Manual resolution (prompts user)
   sync.sync(conflict_resolution=ConflictResolution.MANUAL)