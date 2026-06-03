====
Sync
====

The sync module provides functionality for bidirectional synchronization between local database and Pinboard.in.

BidirectionalSync
=================

Remote posts are mirrored into the local database through the local mirror module,
which reuses the same ``upsert_pinboard_post`` path as direct API imports.

.. autoclass:: pinboard_tools.sync.bidirectional.BidirectionalSync
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pinboard_tools.sync.bidirectional.SyncDirection
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: pinboard_tools.sync.bidirectional.ConflictResolution
   :members:
   :undoc-members:
   :show-inheritance:

PinboardAPI
===========

.. autoclass:: pinboard_tools.sync.api.PinboardAPI
   :members:
   :undoc-members:
   :show-inheritance:

.. autoexception:: pinboard_tools.sync.api.PinboardAPIError
   :members:
   :undoc-members:
   :show-inheritance:
