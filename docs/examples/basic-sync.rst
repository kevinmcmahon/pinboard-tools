==========
Basic Sync
==========

This example demonstrates basic synchronization between your local database and Pinboard.

Setup
=====

.. code-block:: python

   from pinboard_tools import BidirectionalSync, get_session, init_database

   # Initialize database
   init_database("my_bookmarks.db")
   
   # Get database session
   db = get_session()

   # Create sync client with your API token
   sync = BidirectionalSync(db=db, api_token="your_username:your_api_token")

Simple Sync
===========

Perform a basic bidirectional sync:

.. code-block:: python

   # Sync all changes
   results = sync.sync()
   
   print(f"Local to remote: {results['local_to_remote']} bookmarks")
   print(f"Remote to local: {results['remote_to_local']} bookmarks")
   print(f"Conflicts resolved: {results['conflicts_resolved']}")
   print(f"Errors: {results['errors']}")

Dry Run
=======

Test what would be synced without making changes:

.. code-block:: python

   # Dry run - shows what would be synced
   results = sync.sync(dry_run=True)
   
   print("Dry run results:")
   print(f"Would sync {results['local_to_remote']} local changes")
   print(f"Would sync {results['remote_to_local']} remote changes")

One-Way Sync
============

Sync only in one direction:

.. code-block:: python

   from pinboard_tools.sync.bidirectional import SyncDirection

   # Only upload local changes to Pinboard
   results = sync.sync(direction=SyncDirection.LOCAL_TO_REMOTE)
   
   # Only download changes from Pinboard
   results = sync.sync(direction=SyncDirection.REMOTE_TO_LOCAL)

Error Handling
==============

Handle sync errors gracefully:

.. code-block:: python

   try:
       results = sync.sync()
       
       if results['errors'] > 0:
           print(f"Warning: {results['errors']} errors occurred during sync")
       else:
           print("Sync completed successfully!")
           
   except Exception as e:
       print(f"Sync failed: {e}")

Complete Example
================

.. code-block:: python

   #!/usr/bin/env python3
   """
   Complete sync example with error handling and logging.
   """
   
   import os
   import sys
   from pinboard_tools import BidirectionalSync, get_session, init_database
   from pinboard_tools.sync.bidirectional import SyncDirection, ConflictResolution

   def main():
       # Get API token from environment
       api_token = os.getenv("PINBOARD_API_TOKEN")
       if not api_token:
           print("Error: PINBOARD_API_TOKEN environment variable not set")
           sys.exit(1)
       
       try:
           # Initialize database
           db_path = "bookmarks.db"
           init_database(db_path)
           print(f"Database initialized: {db_path}")
           
           # Get database session
           db = get_session()
           
           # Create sync client
           sync = BidirectionalSync(db=db, api_token=api_token)
           print("Sync client created")
           
           # Perform sync
           print("Starting sync...")
           results = sync.sync(
               direction=SyncDirection.BIDIRECTIONAL,
               conflict_resolution=ConflictResolution.NEWEST_WINS,
               dry_run=False
           )
           
           # Report results
           print("\\nSync Results:")
           print(f"  Local → Remote: {results['local_to_remote']}")
           print(f"  Remote → Local: {results['remote_to_local']}")
           print(f"  Conflicts: {results['conflicts_resolved']}")
           print(f"  Errors: {results['errors']}")
           
           if results['errors'] == 0:
               print("\\n✅ Sync completed successfully!")
           else:
               print(f"\\n⚠️  Sync completed with {results['errors']} errors")
               
       except Exception as e:
           print(f"\\n❌ Sync failed: {e}")
           sys.exit(1)

   if __name__ == "__main__":
       main()