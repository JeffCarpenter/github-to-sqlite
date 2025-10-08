# Development notes

# Repository Guidelines

## Project Structure & Module Organization
- Primary CLI entry point is `github_to_sqlite/cli.py`; keep commands thin wrappers that delegate persistence to `github_to_sqlite/utils.py`.
- `utils.py` owns `fetch_*` GitHub API helpers, matching `save_*` routines, and `ensure_db_shape()` which aligns tables, full-text search, and views after writes.
- Tests live in `tests/`, using fixture JSON payloads and verifying SQLite schemas via `sqlite_utils`. Reference these when adding new ingest flows or schema updates.
- `.github/copilot-instructions.md` contains further agent instructions
- `PLAN.md` contains a plan to implement embeddings for starred repositories.

## Build, Test, and Development Commands
- `python -m pip install -e .[test]` installs runtime and testing dependencies in editable mode.
- `pytest` executes unit and integration tests, including CLI runs under `CliRunner` and SQLite assertions.
- `github-to-sqlite --help` lists available subcommands; mimic existing CLI patterns when introducing new ones.

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and descriptive, snake_case names. CLI commands stay kebab-case to match Click usage.
- Add new ingest logic as paired `fetch_*`/`save_*` helpers, normalize GitHub payloads by stripping `*_url` fields, and reuse `save_user()`/`save_repo()` to avoid duplication.
- Favor concise inline comments ahead of complex normalization or relationship handling blocks; keep docstrings focused on argument behavior and side effects.

## Testing Guidelines
- Name tests `test_<feature>.py` and isolate fixtures in JSON alongside tests. Prefer in-memory databases via `sqlite_utils.Database(memory=True)` unless file-backed tables are required.
- Mock GitHub responses with `requests_mock` and call `ensure_db_shape()` within tests to surface schema regressions and FTS/view drift.
- Aim to cover new tables, foreign keys, and many-to-many joins by asserting both row contents and `ForeignKey` metadata.

## Commit & Pull Request Guidelines
- Use short, imperative commit subjects (e.g., `Disable scheduled publish`, `Release 2.9`). Group related changes per commit to simplify review.
- Pull requests should summarize the intent, list affected commands/tables, link any issues, and note testing performed (`pytest`, targeted CLI runs, etc.). Provide schema migration notes when altering database shape.

## Security & Configuration Tips
- Never commit tokens or `auth.json`. Load credentials via `github-to-sqlite auth`, `--auth`, or the `GITHUB_TOKEN` environment variable.
- Respect existing rate-limit handling and headers; when extending API coverage, honor backoff patterns and add flags for expensive network operations (mirroring `--fetch` in the emojis command).
