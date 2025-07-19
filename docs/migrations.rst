Migrations and build files
==========================

Run the ``migrate`` command to create any optional tables and indexes used by the embeddings feature:

.. code-block:: console

    $ github-to-sqlite migrate github.db

This sets up the ``repo_embeddings``, ``readme_chunk_embeddings``, ``repo_build_files`` and ``repo_metadata`` tables. The helper prefers the ``sqlite-vec`` extension when available.

Build file detection
--------------------

Some commands look for standard build definitions such as ``pyproject.toml`` or ``package.json``. The ``find_build_files()`` helper uses the ``fd`` command if installed, otherwise falling back to ``find`` or a Python implementation. You can pass custom patterns to ``find_build_files()`` or supply ``--pattern`` when running ``starred-embeddings``.
