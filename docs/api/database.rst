========
Database
========

The database module provides models and connection management for SQLite storage.

Models
======

.. autoclass:: pinboard_tools.database.models.Bookmark
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pinboard_tools.database.models.Tag
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pinboard_tools.database.models.BookmarkTag
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pinboard_tools.database.models.TagMerge
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pinboard_tools.database.models.SyncStatus
   :members:
   :undoc-members:
   :show-inheritance:

Database Connection
===================

.. autoclass:: pinboard_tools.database.models.Database
   :members:
   :undoc-members:
   :show-inheritance:

.. autofunction:: pinboard_tools.database.models.init_database

.. autofunction:: pinboard_tools.database.models.get_session

Type Definitions
================

.. autoclass:: pinboard_tools.database.models.BookmarkRow
   :members:
   :undoc-members:

.. autoclass:: pinboard_tools.database.models.TagRow
   :members:
   :undoc-members:

.. autoclass:: pinboard_tools.database.models.BookmarkTagRow
   :members:
   :undoc-members:

.. autoclass:: pinboard_tools.database.models.TagMergeRow
   :members:
   :undoc-members:

Helper Functions
================

.. autofunction:: pinboard_tools.database.models.bookmark_from_row

.. autofunction:: pinboard_tools.database.models.tag_from_row

.. autofunction:: pinboard_tools.database.models.bookmark_tag_from_row

Tag Utility Functions
=====================

These functions provide a clean API for working with tags in their normalized form:

.. autofunction:: pinboard_tools.database.models.get_bookmark_tags

.. autofunction:: pinboard_tools.database.models.get_bookmark_tags_string

.. autofunction:: pinboard_tools.database.models.set_bookmark_tags

.. autofunction:: pinboard_tools.database.models.bookmark_with_tags

Queries
=======

.. automodule:: pinboard_tools.database.queries
   :members:
   :undoc-members:
   :show-inheritance: