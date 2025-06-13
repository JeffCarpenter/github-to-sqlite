# Embeddings feature plan

This document decomposes the work required to generate sentence-transformer embeddings for starred repositories. The work is split into three phases so that core functionality lands first, then documentation tooling, followed by publishing the new docs.

## Phase 1: Generate and store embeddings

This phase introduces embeddings for starred repositories. The following
checkboxes track progress for each task.

### Dependencies
- [x] **Add runtime dependencies**
  - [x] Install `sentence-transformers` for embedding inference.
  - [x] Install `sqlite-vec` to store and query embedding vectors in SQLite.
  - [x] Install `semantic-chunkers` from GitHub to chunk README text using
    `semantic_chunkers.chunkers.StatisticalChunker`.
  - [x] Install `fd` to locate build definition files across the repository tree.
    `find_build_files()` prefers `fd` but falls back to `find` or `os.walk` if
    needed.
- [x] **Add development dependencies**
  - [x] Include `pytest-cov` for coverage reports.
  - [x] Update `setup.py` or `pyproject.toml` accordingly.

### Database changes
- [x] **Create `repo_embeddings` table**
  - [x] Columns: `repo_id` (FK to `repos`), `title_embedding`, `description_embedding`, `readme_embedding`.
  - [x] Store embeddings using `sqlite-vec` vec0 virtual tables for efficient vector search.
  - [x] Add indexes on `repo_id` for fast lookup.
- [x] **Create `readme_chunk_embeddings` table**
  - [x] Columns: `repo_id` (FK to `repos`), `chunk_index`, `chunk_text`, `embedding`.
  - [x] Use `sqlite-vec` for the `embedding` column to enable similarity search over
    individual README chunks.
  - [x] Add a composite index on `repo_id` and `chunk_index`.
- [x] **Create `repo_build_files` table**
  - [x] Columns: `repo_id` (FK to `repos`), `file_path`, `metadata` (JSON).
  - [x] Store one row per build definition (e.g. `pyproject.toml`, `package.json`).
  - [x] The `metadata` column captures the entire parsed contents of the file so that
    fields such as package name or author can be queried later.
- [x] **Create `repo_metadata` table**
  - [x] Columns: `repo_id` (FK to `repos`), `language`, `directory_tree`.
  - [x] Capture the primary programming language and a serialized directory structure
    for quick reference.
 - [x] **Migration script**
  - [x] Provide SQL script or CLI command that creates the table if it does not exist.
  - [x] Document migration process in README.

### Embedding generation
- [x] **Model loading**
  - [x] Default to `huggingface.co/Alibaba-NLP/gte-modernbert-base`.
  - [x] Allow overriding the model path via CLI option or environment variable.
- [x] **Data collection**
  - [x] Fetch starred repositories from GitHub using existing API utilities.
  - [x] Retrieve README HTML or markdown for each repo.
  - [x] Locate common build files (`pyproject.toml`, `package.json`,
    `Cargo.toml`, `Gemfile`) using `fd` when available, otherwise `find` or
    `os.walk`.
  - [x] Parse each file and store its entire contents as JSON in the
    `repo_build_files.metadata` column. Package name and author can then be
    derived from this JSON as needed.
  - [x] Record the repository's primary programming language and generate a serialized
    directory tree for storage in `repo_metadata`.
- [x] **Chunking**
  - [x] Use `semantic_chunkers.chunkers.StatisticalChunker` to split README text
    into semantically meaningful chunks. See `docs/00-chunkers-intro.ipynb` in
    the `semantic-chunkers` repository for usage examples.
  - [x] If that library is not available at runtime, fall back to splitting on
    blank lines to ensure tests run without optional dependencies.
- [x] **Vector inference**
  - [x] Run the model on the repository title, description and each README chunk.
  - [x] Batch requests when possible to speed up inference.
- [x] **Storage**
  - [x] Save repository-level vectors to `repo_embeddings`.
  - [x] Save each chunk's embedding to `readme_chunk_embeddings` along with the
    chunk text and index.
  - [x] Skip entries that already exist unless `--force` is supplied.

### CLI integration
- [x] **New command** `starred-embeddings`
  - [x] Accept database path and optional model path.
  - [x] Iterate through all starred repos and compute embeddings.
  - [x] Chunk each README using `StatisticalChunker` and store chunk embeddings.
  - [x] Collect build metadata using `find_build_files()` (using `fd`, `find` or
    `os.walk` as available) and store the entire parsed JSON in the
    `repo_build_files.metadata` column.
  - [x] Support `--force` and `--verbose` flags.
- [x] **Error handling**
  - [x] Handle missing READMEs gracefully.
  - [x] Retry transient network failures.

### Testing
- [x] **Unit tests**
  - [x] Mock GitHub API calls and README fetches.
  - [x] Verify embeddings are generated and stored correctly, including per-chunk
    embeddings.
  - [x] Ensure build metadata is parsed and stored as JSON in `repo_build_files`.
  - [x] **Coverage**
  - [x] Run `pytest --cov --cov-branch` in CI to ensure branch coverage does not regress.

### Documentation
- [x] **README updates**
  - [x] Describe the new command and its options.
  - [x] Mention default model and how to override it.
  - [x] Document how README files are chunked using `semantic-chunkers` before
    embedding.
  - [x] Explain how build files are detected using `find_build_files()`
    (preferring `fd`) and stored for analysis.
- [x] **Changelog entry**
  - [x] Summarize the feature and dependencies.

## Phase 2: Documentation tooling

- [x] **Introduce RST and Sphinx**
  - [x] Add `sphinx` and `sphinx-rtd-theme` to development dependencies.
  - [x] Configure a `docs/` directory with Sphinx `conf.py` and initial structure.
- [x] **Convert existing documentation**
  - [x] Migrate `README.md` or relevant guides into RST as needed.
  - [x] Ensure the embeddings feature is documented in the new docs site.
- [ ] **Automation**
  - [ ] Update CI to build documentation and fail on warnings.

## Phase 3: Publish documentation

- [ ] **Deployment**
  - [ ] Publish the documentation using GitHub Pages or another hosting service.
  - [ ] Automate deployment on release so new docs are available immediately.

## Next task: publish documentation site

With the documentation building in CI, the next step is to publish it so users
can browse the docs online.

Steps:

- [ ] Set up a GitHub Pages workflow that uploads ``docs/_build``
  from the main branch.
- [ ] Trigger the deployment after tests pass on ``main``.

Completed build steps:

- [x] Install documentation dependencies in the CI environment.
- [x] Run ``sphinx-build -b html docs docs/_build`` during CI.
- [x] Treat warnings as errors so the build fails on broken docs.

- [x] Add a `starred-embeddings` Click command in `cli.py`.
  - [x] Accept a database path argument.
  - [x] Accept `--model` to override the default model.
  - [x] Support `--force` and `--verbose` flags.
- [x] Load the sentence-transformers model using the configured name.
- [x] Iterate through starred repositories using existing API helpers.
  - [x] Save repository metadata to the database.
  - [x] Fetch README content for each repository.
  - [x] Use `StatisticalChunker` to split README text.
  - [x] Run embeddings for titles, descriptions and README chunks.
  - [x] Save vectors to `repo_embeddings` and `readme_chunk_embeddings`.
  - [x] Extract build files using `find_build_files()` and store metadata in
    `repo_build_files`.
  - [x] Capture the primary language and directory tree in `repo_metadata`.
- [x] Write unit tests for the new command using mocks to avoid network calls.
  - [x] Ensure coverage passes with `pytest --cov --cov-branch`.
  - [x] Add tests for utility helpers like `vector_to_blob`, `parse_build_file`,
    `directory_tree` and `_maybe_load_sqlite_vec`.

