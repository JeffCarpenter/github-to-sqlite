"""Test Typer Context functionality for dependency injection."""
import json
import pathlib
import sqlite_utils
from typer.testing import CliRunner
from github_to_sqlite import cli


def test_context_state_initialization(requests_mock, tmpdir):
    """Test that Context state is properly initialized."""
    # Load actual repo fixture to get complete data
    repo_data = json.load(open(pathlib.Path(__file__).parent / "repo.json"))
    
    # Mock the API responses for repos command
    requests_mock.get(
        "https://api.github.com/repos/dogsheep/github-to-sqlite",
        json=repo_data,
    )
    
    runner = CliRunner()
    db_path = str(tmpdir / "test.db")
    
    # Create auth file
    auth_path = tmpdir / "auth.json"
    auth_path.write_text(json.dumps({"github_personal_token": "test_token"}), "utf-8")
    
    # Run command (global options before command name)
    result = runner.invoke(
        cli.app,
        ["--db", db_path, "-a", str(auth_path), "repos", "-r", "dogsheep/github-to-sqlite"],
    )
    
    assert result.exit_code == 0
    
    # Verify database was created and has expected structure
    db = sqlite_utils.Database(db_path)
    assert "repos" in db.table_names()
    assert db["repos"].count == 1


def test_context_token_reuse(requests_mock, tmpdir):
    """Test that token is properly loaded and reused via Context."""
    # Load actual repo fixture
    repo_data = json.load(open(pathlib.Path(__file__).parent / "repo.json"))
    
    # Mock the API responses
    repo_mock = requests_mock.get(
        "https://api.github.com/repos/dogsheep/github-to-sqlite",
        json=repo_data,
    )
    
    runner = CliRunner()
    db_path = str(tmpdir / "test.db")
    
    # Create auth file
    auth_path = tmpdir / "auth.json"
    auth_path.write_text(json.dumps({"github_personal_token": "my_token"}), "utf-8")
    
    # Run command (global options before command name)
    result = runner.invoke(
        cli.app,
        ["--db", db_path, "-a", str(auth_path), "repos", "-r", "dogsheep/github-to-sqlite"],
    )
    
    assert result.exit_code == 0
    
    # Verify token was used in the API call
    assert repo_mock.called
    assert "token my_token" == repo_mock.last_request.headers["authorization"]


def test_context_db_reuse(requests_mock, tmpdir):
    """Test that database connection is reused via Context within a command."""
    # Load actual fixtures
    repo_data = json.load(open(pathlib.Path(__file__).parent / "repo.json"))
    releases_data = json.load(open(pathlib.Path(__file__).parent / "releases.json"))
    
    # Mock the API responses
    requests_mock.get(
        "https://api.github.com/repos/dogsheep/github-to-sqlite",
        json=repo_data,
    )
    requests_mock.get(
        "https://api.github.com/repos/dogsheep/github-to-sqlite/releases",
        json=releases_data[:1],  # Use first release from fixtures
    )
    
    runner = CliRunner()
    db_path = str(tmpdir / "test.db")
    
    # Create auth file
    auth_path = tmpdir / "auth.json"
    auth_path.write_text(json.dumps({"github_personal_token": "test_token"}), "utf-8")
    
    # Run command (global options before command name)
    result = runner.invoke(
        cli.app,
        ["--db", db_path, "-a", str(auth_path), "releases", "dogsheep/github-to-sqlite"],
    )
    
    assert result.exit_code == 0
    
    # Verify database was created and contains data
    db = sqlite_utils.Database(db_path)
    assert "repos" in db.table_names()
    assert "releases" in db.table_names()
    assert db["releases"].count == 1


def test_context_multiple_commands_share_state(requests_mock, tmpdir):
    """Test that running multiple commands sequentially works correctly."""
    # Load actual fixtures
    repo_data = json.load(open(pathlib.Path(__file__).parent / "repo.json"))
    releases_data = json.load(open(pathlib.Path(__file__).parent / "releases.json"))
    
    # Mock for first command (repos)
    requests_mock.get(
        "https://api.github.com/repos/dogsheep/github-to-sqlite",
        json=repo_data,
    )
    
    # Mock for second command (releases)
    requests_mock.get(
        "https://api.github.com/repos/dogsheep/github-to-sqlite/releases",
        json=releases_data[:1],  # Use first release from fixtures
    )
    
    runner = CliRunner()
    db_path = str(tmpdir / "test.db")
    
    # Create auth file
    auth_path = tmpdir / "auth.json"
    auth_path.write_text(json.dumps({"github_personal_token": "test_token"}), "utf-8")
    
    # Run first command (global options before command name)
    result1 = runner.invoke(
        cli.app,
        ["--db", db_path, "-a", str(auth_path), "repos", "-r", "dogsheep/github-to-sqlite"],
    )
    assert result1.exit_code == 0
    
    # Run second command (should work with same database)
    result2 = runner.invoke(
        cli.app,
        ["--db", db_path, "-a", str(auth_path), "releases", "dogsheep/github-to-sqlite"],
    )
    assert result2.exit_code == 0
    
    # Verify both commands updated the same database
    db = sqlite_utils.Database(db_path)
    assert "repos" in db.table_names()
    assert "releases" in db.table_names()
    assert db["repos"].count == 1
    assert db["releases"].count == 1
