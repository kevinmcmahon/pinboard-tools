==============
Pinboard Tools
==============

A Python library for syncing and managing Pinboard bookmarks with advanced analysis capabilities.

Features
========

- **Bidirectional Sync**: Keep your local database in sync with Pinboard.in
- **Tag Analysis**: Detect similar tags and consolidate duplicates
- **Full-Text Search**: SQLite FTS5-powered search across all bookmark content
- **Rate Limiting**: Built-in API rate limiting for Pinboard compatibility
- **Type Safety**: Comprehensive type hints throughout the codebase

Quick Start
===========

Installation
------------

.. code-block:: bash

   pip install pinboard-tools

Basic Usage
-----------

.. code-block:: python

   from pinboard_tools import BidirectionalSync, get_session, init_database

   # Initialize database
   init_database("bookmarks.db")
   
   # Get database session
   db = get_session()

   # Create sync client
   sync = BidirectionalSync(db=db, api_token="your_pinboard_token")

   # Perform bidirectional sync
   results = sync.sync()
   print(f"Synced {results['local_to_remote']} local changes")
   print(f"Synced {results['remote_to_local']} remote changes")

API Reference
=============

.. toctree::
   :maxdepth: 2

   api/sync
   api/database
   api/analysis
   api/utils

User Guide
==========

.. toctree::
   :maxdepth: 2

   guide/installation
   guide/configuration

Examples
========

.. toctree::
   :maxdepth: 2

   examples/basic-sync
   examples/tag-management

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`