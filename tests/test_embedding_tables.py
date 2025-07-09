import sqlite_utils
from github_to_sqlite import utils


def test_embedding_tables_created():
    db = sqlite_utils.Database(memory=True)
    utils.ensure_db_shape(db)
    tables = set(db.table_names())
    assert {
        "repo_embeddings",
        "readme_chunk_embeddings",
        "repo_build_files",
        "repo_metadata",
    }.issubset(tables)
