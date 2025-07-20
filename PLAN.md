# Embeddings feature plan

This document tracks the remaining work needed to generate sentence-transformer embeddings for starred repositories.

## Phase 1: Generate and store embeddings

### Dependencies
- [ ] Install `fd` to locate build definition files across the repository tree.

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
    `repo_build_files.metadata` column.
  - [ ] Record the repository's primary programming language and generate a
    serialized directory tree for storage in `repo_metadata`.
- [ ] **Chunking**
  - [ ] Use `semantic_chunkers.chunkers.StatisticalChunker` to split README text
    into semantically meaningful chunks. If that library is unavailable at
    runtime, fall back to splitting on blank lines.
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
  - [ ] Collect build metadata using `fd` and store the parsed JSON in
    `repo_build_files.metadata`.
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
- [ ] Introduce RST and Sphinx for publishing a docs site.
- [ ] Convert existing documentation into RST.
- [ ] Update CI to build docs and fail on warnings.

## Phase 3: Publish documentation
- [ ] Deploy the docs using GitHub Pages or another hosting service.
- [ ] Automate deployment on release so new docs are available immediately.

## Next task: implement `starred-embeddings` CLI
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
