from click.testing import CliRunner
import sqlite_utils
from github_to_sqlite import cli


def test_migrate_creates_tables(tmpdir):
    db_path = str(tmpdir / "test.db")
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["migrate", db_path])
    assert result.exit_code == 0
    db = sqlite_utils.Database(db_path)
    tables = set(db.table_names())
    assert {
        "repo_embeddings",
        "readme_chunk_embeddings",
        "repo_build_files",
        "repo_metadata",
    }.issubset(tables)
