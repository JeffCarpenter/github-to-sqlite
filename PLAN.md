# Embeddings feature plan

This document decomposes the work required to generate sentence-transformer embeddings for starred repositories. Each bullet point expands into further tasks until reaching granular actionable steps.

## 1. Dependencies
- **Add runtime dependencies**
  - Install `sentence-transformers` for embedding inference.
  - Install `sqlite-vec` to store and query embedding vectors in SQLite.
- **Add development dependencies**
  - Include `pytest-cov` for coverage reports.
  - Update `setup.py` or `pyproject.toml` accordingly.
  - Plan to add RST and Sphinx documentation tooling in a future iteration.

## 2. Database changes
- **Create `repo_embeddings` table**
  - Columns: `repo_id` (FK to `repos`), `title_embedding`, `description_embedding`, `readme_embedding`.
  - Store embeddings using `sqlite-vec` vec0 virtual tables for efficient vector search.
  - Add indexes on `repo_id` for fast lookup.
- **Migration script**
  - Provide SQL script or CLI command that creates the table if it does not exist.
  - Document migration process in README.

## 3. Embedding generation
- **Model loading**
  - Default to `huggingface.co/Alibaba-NLP/gte-modernbert-base`.
  - Allow overriding the model path via CLI option or environment variable.
- **Data collection**
  - Fetch starred repositories from GitHub using existing API utilities.
  - Retrieve README HTML or markdown for each repo.
- **Vector inference**
  - Run the model on the repository title, description and README.
  - Batch requests when possible to speed up inference.
- **Storage**
  - Save computed vectors to `repo_embeddings`.
  - Skip entries that already exist unless `--force` is supplied.

## 4. CLI integration
- **New command** `starred-embeddings`
  - Accept database path and optional model path.
  - Iterate through all starred repos and compute embeddings.
  - Support `--force` and `--verbose` flags.
- **Error handling**
  - Handle missing READMEs gracefully.
  - Retry transient network failures.

## 5. Testing
- **Unit tests**
  - Mock GitHub API calls and README fetches.
  - Verify embeddings are generated and stored correctly.
- **Coverage**
  - Run `pytest --cov` in CI to ensure coverage does not regress.

## 6. Documentation
- **README updates**
  - Describe the new command and its options.
  - Mention default model and how to override it.
- **Changelog entry**
  - Summarize the feature and dependencies.

