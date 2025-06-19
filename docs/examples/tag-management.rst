===============
Tag Management
===============

This example demonstrates working with tags using the normalized tag storage system.

Understanding Tag Storage
=========================

Tags are stored in normalized form using a many-to-many relationship between bookmarks and tags. This enables powerful querying and analysis while maintaining compatibility with the Pinboard.in API.

.. note::
   Tags are automatically normalized (lowercased and whitespace-trimmed) when stored. Tag strings for API calls are generated dynamically from the normalized storage.

Working with Tags
=================

Getting Tags for a Bookmark
----------------------------

.. code-block:: python

   from pinboard_tools.database.models import get_bookmark_tags, get_bookmark_tags_string

   # Get tags as a list
   tags = get_bookmark_tags(db, bookmark_id)
   print(f"Tags: {tags}")  # ['python', 'web', 'development']

   # Get tags as space-separated string (for API calls)
   tags_string = get_bookmark_tags_string(db, bookmark_id)
   print(f"Tags string: {tags_string}")  # "python web development"

Setting Tags for a Bookmark
----------------------------

.. code-block:: python

   from pinboard_tools.database.models import set_bookmark_tags

   # Set tags (replaces existing tags)
   new_tags = ['python', 'flask', 'tutorial']
   set_bookmark_tags(db, bookmark_id, new_tags)

   # Tags are automatically normalized
   messy_tags = ['  Python  ', 'FLASK', 'Tutorial  ']
   set_bookmark_tags(db, bookmark_id, messy_tags)
   # Results in: ['python', 'flask', 'tutorial']

Getting Bookmarks with Tags
----------------------------

.. code-block:: python

   from pinboard_tools.database.models import bookmark_with_tags

   # Get a bookmark with its tags populated
   bookmark = bookmark_with_tags(db, bookmark_id)
   if bookmark and bookmark._tags:
       print(f"Bookmark: {bookmark.description}")
       print(f"Tags: {bookmark._tags}")

Tag Analysis and Consolidation
==============================

Finding Similar Tags
---------------------

.. code-block:: python

   from pinboard_tools.analysis.consolidation import TagConsolidator

   consolidator = TagConsolidator(db)
   analysis = consolidator.analyze_tags()

   print(f"Total tags: {analysis['total_tags']}")
   print("\\nSimilar tags found:")
   for tag, similarities in analysis['similarities'].items():
       for similar_tag, score, reason in similarities:
           print(f"  {tag} ↔ {similar_tag} (score: {score:.2f}, {reason})")

Merging Tags
------------

.. code-block:: python

   # Merge 'javascript' into 'js'
   result = consolidator.merge_tags('javascript', 'js', dry_run=False)
   
   if result['success']:
       print(f"Merged {result['bookmarks_updated']} bookmarks")
   else:
       print(f"Merge failed: {result.get('error', 'Unknown error')}")

   # Dry run to see what would be merged
   result = consolidator.merge_tags('python3', 'python', dry_run=True)
   print(f"Would update {result['bookmarks_updated']} bookmarks")

Querying Tags
=============

Finding Bookmarks by Tags
--------------------------

.. code-block:: python

   # Find bookmarks with specific tags
   cursor = db.execute("""
       SELECT b.*, GROUP_CONCAT(t.name, ' ') as tags
       FROM bookmarks b
       JOIN bookmark_tags bt ON b.id = bt.bookmark_id
       JOIN tags t ON bt.tag_id = t.id
       WHERE t.name IN ('python', 'web')
       GROUP BY b.id
   """)
   
   for row in cursor:
       print(f"{row['description']} - Tags: {row['tags']}")

Tag Usage Statistics
--------------------

.. code-block:: python

   # Get tag usage counts
   cursor = db.execute("""
       SELECT t.name, COUNT(bt.bookmark_id) as usage_count
       FROM tags t
       LEFT JOIN bookmark_tags bt ON t.id = bt.tag_id
       GROUP BY t.id
       ORDER BY usage_count DESC
       LIMIT 20
   """)
   
   print("Most used tags:")
   for row in cursor:
       print(f"  {row['name']}: {row['usage_count']} bookmarks")

Finding Unused Tags
-------------------

.. code-block:: python

   # Find tags not used by any bookmarks
   cursor = db.execute("""
       SELECT t.name
       FROM tags t
       LEFT JOIN bookmark_tags bt ON t.id = bt.tag_id
       WHERE bt.tag_id IS NULL
   """)
   
   unused_tags = [row['name'] for row in cursor]
   if unused_tags:
       print(f"Unused tags: {', '.join(unused_tags)}")

Migration from String-based Tags
================================

If you have existing code that worked with tag strings, here's how to migrate:

Before (using tag strings):
---------------------------

.. code-block:: python

   # Old way - directly accessing tags field
   cursor = db.execute("SELECT tags FROM bookmarks WHERE id = ?", (bookmark_id,))
   tags_string = cursor.fetchone()['tags']
   tags = tags_string.split() if tags_string else []

After (using normalized tags):
------------------------------

.. code-block:: python

   # New way - using utility functions
   from pinboard_tools.database.models import get_bookmark_tags, get_bookmark_tags_string

   # Get as list
   tags = get_bookmark_tags(db, bookmark_id)
   
   # Get as string (for API compatibility)
   tags_string = get_bookmark_tags_string(db, bookmark_id)

Setting Tags Migration:
-----------------------

.. code-block:: python

   # Old way - direct SQL manipulation
   tags_string = "python web development"
   db.execute("UPDATE bookmarks SET tags = ? WHERE id = ?", (tags_string, bookmark_id))

   # New way - using utility function
   from pinboard_tools.database.models import set_bookmark_tags
   
   tags = ["python", "web", "development"]
   set_bookmark_tags(db, bookmark_id, tags)

Best Practices
==============

1. **Use Utility Functions**: Always use the provided tag utility functions instead of direct SQL manipulation.

2. **Tag Normalization**: Remember that tags are automatically normalized (lowercased, trimmed).

3. **Batch Operations**: For bulk tag operations, consider using transactions for better performance.

4. **Sync Awareness**: Tag modifications automatically mark bookmarks for sync with Pinboard.in.

5. **Analysis Tools**: Use the consolidation tools to keep your tag vocabulary clean and consistent.