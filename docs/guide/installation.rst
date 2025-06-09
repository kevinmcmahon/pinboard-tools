============
Installation
============

Requirements
============

- Python 3.11 or higher
- SQLite 3.35+ (for FTS5 support)

Installation Methods
====================

From PyPI (recommended)
-----------------------

.. code-block:: bash

   pip install pinboard-tools

From Source
-----------

.. code-block:: bash

   git clone https://github.com/your-username/pinboard-tools.git
   cd pinboard-tools
   uv sync
   uv run pip install -e .

Development Installation
========================

For development, install with development dependencies:

.. code-block:: bash

   git clone https://github.com/your-username/pinboard-tools.git
   cd pinboard-tools
   uv sync --dev

Verification
============

Verify your installation:

.. code-block:: python

   import pinboard_tools
   print(pinboard_tools.__version__)

Dependencies
============

Core Dependencies
-----------------

- **requests**: HTTP client for Pinboard API
- **sqlite3**: Built-in database support

Development Dependencies
------------------------

- **pytest**: Testing framework
- **mypy**: Type checking
- **ruff**: Code formatting and linting
- **sphinx**: Documentation generation