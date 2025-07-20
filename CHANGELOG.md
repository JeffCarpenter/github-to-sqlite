# Changelog

## Unreleased

### Added
- `migrate` CLI command to create embedding tables.
- Embedding tables: `repo_embeddings`, `readme_chunk_embeddings`, `repo_build_files` and `repo_metadata`.
- Utilities to automatically load `sqlite-vec` and ensure tables exist.
- Chunking helpers `BasicSentencizerChunker` and `SimpleChunker`.
- Optional dependencies for embedding generation (`sentence-transformers`, `sqlite-vec`, `nltk`, `onnx`, `pydantic`, `tokenizers`).

### Changed
- Database setup now includes embedding tables via `utils.ensure_db_shape`.
