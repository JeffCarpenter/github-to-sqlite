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
  - [ ] Install `fd` to locate build definition files across the repository tree.
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
- [ ] **Model loading**
  - [ ] Default to `huggingface.co/Alibaba-NLP/gte-modernbert-base`.
  - [ ] Allow overriding the model path via CLI option or environment variable.
- [ ] **Data collection**
  - [ ] Fetch starred repositories from GitHub using existing API utilities.
  - [ ] Retrieve README HTML or markdown for each repo.
  - [ ] Use `fd` to locate common build files (`pyproject.toml`, `package.json`,
    `Cargo.toml`, `Gemfile`).
  - [ ] Parse each file and store its entire contents as JSON in the
    `repo_build_files.metadata` column. Package name and author can then be
    derived from this JSON as needed.
  - [ ] Record the repository's primary programming language and generate a serialized
    directory tree for storage in `repo_metadata`.
- [ ] **Chunking**
  - [ ] Use `semantic_chunkers.chunkers.StatisticalChunker` to split README text
    into semantically meaningful chunks. See `docs/00-chunkers-intro.ipynb` in
    the `semantic-chunkers` repository for usage examples.
  - [ ] If that library is not available at runtime, fall back to splitting on
    blank lines to ensure tests run without optional dependencies.
- [ ] **Vector inference**
  - [ ] Run the model on the repository title, description and each README chunk.
  - [ ] Batch requests when possible to speed up inference.
- [ ] **Storage**
  - [ ] Save repository-level vectors to `repo_embeddings`.
  - [ ] Save each chunk's embedding to `readme_chunk_embeddings` along with the
    chunk text and index.
  - [ ] Skip entries that already exist unless `--force` is supplied.

### CLI integration
- [ ] **New command** `starred-embeddings`
  - [ ] Accept database path and optional model path.
  - [ ] Iterate through all starred repos and compute embeddings.
  - [ ] Chunk each README using `StatisticalChunker` and store chunk embeddings.
  - [ ] Collect build metadata using `fd` and store the entire parsed JSON in the
    `repo_build_files.metadata` column.
  - [ ] Support `--force` and `--verbose` flags.
- [ ] **Error handling**
  - [ ] Handle missing READMEs gracefully.
  - [ ] Retry transient network failures.

### Testing
- [ ] **Unit tests**
  - [ ] Mock GitHub API calls and README fetches.
  - [ ] Verify embeddings are generated and stored correctly, including per-chunk
    embeddings.
  - [ ] Ensure build metadata is parsed and stored as JSON in `repo_build_files`.
  - [ ] **Coverage**
  - [ ] Run `pytest --cov` in CI to ensure coverage does not regress.

### Documentation
- [ ] **README updates**
  - [ ] Describe the new command and its options.
  - [ ] Mention default model and how to override it.
  - [ ] Document how README files are chunked using `semantic-chunkers` before
    embedding.
  - [ ] Explain how build files are detected with `fd` and stored for analysis.
- [ ] **Changelog entry**
  - [ ] Summarize the feature and dependencies.

## Phase 2: Documentation tooling

- [ ] **Introduce RST and Sphinx**
  - [ ] Add `sphinx` and `sphinx-rtd-theme` to development dependencies.
  - [ ] Configure a `docs/` directory with Sphinx `conf.py` and initial structure.
- [ ] **Convert existing documentation**
  - [ ] Migrate `README.md` or relevant guides into RST as needed.
  - [ ] Ensure the embeddings feature is documented in the new docs site.
- [ ] **Automation**
  - [ ] Update CI to build documentation and fail on warnings.

## Phase 3: Publish documentation

- [ ] **Deployment**
  - [ ] Publish the documentation using GitHub Pages or another hosting service.
  - [ ] Automate deployment on release so new docs are available immediately.

## Next task: implement `starred-embeddings` CLI

The immediate focus is to build the command that generates embeddings for the
user's starred repositories. This high level task expands into the following
steps:

- [ ] Add a `starred-embeddings` Click command in `cli.py`.
  - [ ] Accept a database path argument.
  - [ ] Accept `--model` to override the default model.
  - [ ] Support `--force` and `--verbose` flags.
- [ ] Load the sentence-transformers model using the configured name.
- [ ] Iterate through starred repositories using existing API helpers.
  - [ ] Save repository metadata to the database.
  - [ ] Fetch README content for each repository.
  - [ ] Use `StatisticalChunker` to split README text.
  - [ ] Run embeddings for titles, descriptions and README chunks.
  - [ ] Save vectors to `repo_embeddings` and `readme_chunk_embeddings`.
  - [ ] Extract build files using `fd` and store metadata in `repo_build_files`.
  - [ ] Capture the primary language and directory tree in `repo_metadata`.
- [ ] Write unit tests for the new command using mocks to avoid network calls.
- [ ] Ensure coverage passes with `pytest --cov`.

