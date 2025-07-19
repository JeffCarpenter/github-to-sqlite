Generating embeddings
=====================

The ``starred-embeddings`` command computes sentence-transformer embeddings for repositories you have starred. It loads the model configured in ``config.default_model`` (``Alibaba-NLP/gte-modernbert-base`` by default) unless you specify ``--model`` or set the ``GITHUB_TO_SQLITE_MODEL`` environment variable.

.. code-block:: console

    $ github-to-sqlite starred-embeddings github.db --model my/custom-model

The command stores repository-level vectors in ``repo_embeddings`` and README chunk vectors in ``readme_chunk_embeddings``. Build files discovered via ``find_build_files()`` are parsed and saved to ``repo_build_files``. You can supply additional ``--pattern`` options to search for other build files. Basic language information and the directory listing are recorded in ``repo_metadata``.
