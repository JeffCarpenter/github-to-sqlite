# GitHub Copilot Instructions

## Architecture
- CLI entry point `github_to_sqlite/cli.py` defines Click commands such as `issues`, `pull-requests`, etc.; they orchestrate fetching GitHub data and saving to SQLite.
- GitHub API + persistence live in `github_to_sqlite/utils.py`. Each `fetch_*` helper wraps `requests` + `paginate`, and each `save_*` helper normalizes payloads, resolves foreign keys via `save_user`, and writes with `sqlite_utils`.
- After any write, commands call `utils.ensure_db_shape(db)` to enforce foreign keys, create FTS tables defined in `FTS_CONFIG`, and maintain derived views like `dependent_repos`.

## Key patterns
- New data ingest should add a `fetch_*` generator that yields API payloads and a matching `save_*` routine that strips `*_url` fields, stores related objects (users, milestones, licenses) before inserting, and handles many-to-many via `table.m2m` or `insert_all`.
- Reuse helpers: `save_repo` persists repo + owner/organization, `save_user` tolerates missing names and `None` placeholders, `paginate` automatically adds `per_page=100` and raises custom `GitHubError`.
- `load_token()` reads `auth.json` or `GITHUB_TOKEN`; CLI commands provide `--auth` overrides and some accept `--load` paths for injecting recorded JSON (helps with tests/offline runs).
- Workflow ingestion (`utils.save_workflow`) expects YAML content, replaces prior rows, and fans out into `workflows`, `jobs`, `steps`; follow the cascade when changing schema.

## Developer workflow
- Install deps with `python -m pip install -e .[test]`; optional features like `scrape-dependents` rely on `bs4`.
- Run the suite with `pytest`; integration-style tests live in `tests/` and lean on `requests_mock` to stub GitHub endpoints and `CliRunner().isolated_filesystem()` for CLI exercises.
- Tests typically create in-memory SQLite via `sqlite_utils.Database(memory=True)`, seed fixture JSON from `tests/*.json`, and assert on table contents and `sqlite_utils.db.ForeignKey` objects.
- When adding persistence logic, mirror existing tests by validating both the written rows and the foreign-key metadata, then call `ensure_db_shape` so FTS/views update.

## Data model tips
- Expect tables for issues, pull_requests, releases, tags, commits, stars, dependents, workflows, etc.; `save_*` helpers will `alter=True` to evolve schemas, so keep column types compatible.
- FTS tables and views are generated lazily—only create base tables before asking for search capability or derived views.
- For assets with blobs (e.g., emojis), gate expensive network fetches behind flags (`--fetch`) and batch updates, as done in `cli.emojis`.

## When in doubt
- Prefer enhancing `utils.py`; keep CLI functions thin shells that parse arguments, resolve the target repos via `utils.fetch_repo`, then call the relevant `save_*` helper and `ensure_db_shape`.
- Handle rate limits gently by reusing the existing throttling (`time.sleep(1)` between repo loops) and Accept headers already in use (e.g., `mercy-preview` for topics, `star+json` for starred repos).
