import typer
import datetime
import itertools
import pathlib
import textwrap
import os
import sqlite_utils
import time
import json
from typing import Optional, List
from github_to_sqlite import utils

app = typer.Typer(help="Save data from GitHub to a SQLite database")


def version_callback(value: bool):
    if value:
        version = "2.9"  # Version from setup.py
        typer.echo(f"github-to-sqlite, version {version}")
        raise typer.Exit()


@app.callback()
def cli(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
):
    """Save data from GitHub to a SQLite database"""
    pass


@app.command()
def auth(
    auth_file: str = typer.Option(
        "auth.json",
        "-a",
        "--auth",
        help="Path to save tokens to, defaults to auth.json",
    ),
):
    """Save authentication credentials to a JSON file"""
    typer.echo("Create a GitHub personal user token and paste it here:")
    typer.echo()
    personal_token = typer.prompt("Personal token")
    if pathlib.Path(auth_file).exists():
        auth_data = json.load(open(auth_file))
    else:
        auth_data = {}
    auth_data["github_personal_token"] = personal_token
    open(auth_file, "w").write(json.dumps(auth_data, indent=4) + "\n")


@app.command()
def issues(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repo: str = typer.Argument(..., help="Repository (e.g. simonw/datasette)"),
    issue: Optional[List[int]] = typer.Option(None, help="Just pull these issue numbers"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
    load: Optional[str] = typer.Option(None, help="Load issues JSON from this file instead of the API"),
):
    """Save issues for a specified repository, e.g. simonw/datasette"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    repo_full = utils.fetch_repo(repo, token)
    utils.save_repo(db, repo_full)
    if load:
        issues_data = json.load(open(load))
    else:
        issue_ids = tuple(issue) if issue else ()
        issues_data = utils.fetch_issues(repo, token, issue_ids)

    issues_data = list(issues_data)
    utils.save_issues(db, issues_data, repo_full)
    utils.ensure_db_shape(db)


@app.command(name="pull-requests")
def pull_requests(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repo: Optional[str] = typer.Argument(None, help="Repository (e.g. simonw/datasette)"),
    pull_request: Optional[List[int]] = typer.Option(None, help="Just pull these pull-request numbers"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
    load: Optional[str] = typer.Option(None, help="Load pull-requests JSON from this file instead of the API"),
    org: Optional[List[str]] = typer.Option(None, help="Fetch all pull requests from this GitHub organization"),
    state: Optional[str] = typer.Option(None, help="Only fetch pull requests in this state"),
    search: Optional[str] = typer.Option(None, help="Find pull requests with a search query"),
):
    """Save pull_requests for a specified repository, e.g. simonw/datasette"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    pull_request_ids = tuple(pull_request) if pull_request else ()
    orgs = org if org else ()
    
    if load:
        repo_full = utils.fetch_repo(repo, token)
        utils.save_repo(db, repo_full)
        pull_requests_data = json.load(open(load))
        utils.save_pull_requests(db, pull_requests_data, repo_full)
    elif search:
        repos_seen = set()
        search += " is:pr"
        pull_requests_data = utils.fetch_searched_pulls_or_issues(search, token)
        for pull_request_item in pull_requests_data:
            pr_repo_url = pull_request_item["repository_url"]
            if pr_repo_url not in repos_seen:
                pr_repo = utils.fetch_repo(url=pr_repo_url)
                utils.save_repo(db, pr_repo)
                repos_seen.add(pr_repo_url)
            utils.save_pull_requests(db, [pull_request_item], pr_repo)
    else:
        if orgs:
            repos = itertools.chain.from_iterable(
                utils.fetch_all_repos(token=token, org=org_name)
                for org_name in orgs
            )
        else:
            repos = [utils.fetch_repo(repo, token)]
        for repo_full in repos:
            utils.save_repo(db, repo_full)
            repo_name = repo_full["full_name"]
            pull_requests_data = utils.fetch_pull_requests(repo_name, state, token, pull_request_ids)
            utils.save_pull_requests(db, pull_requests_data, repo_full)
    utils.ensure_db_shape(db)


@app.command(name="issue-comments")
def issue_comments(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repo: str = typer.Argument(..., help="Repository (e.g. simonw/datasette)"),
    issue: Optional[str] = typer.Option(None, help="Just pull comments for this issue"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
):
    """Retrieve issue comments for a specific repository"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    for comment in utils.fetch_issue_comments(repo, token, issue):
        utils.save_issue_comment(db, comment)
    utils.ensure_db_shape(db)


@app.command()
def starred(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    username: Optional[str] = typer.Argument(None, help="GitHub username"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
    load: Optional[str] = typer.Option(None, help="Load issues JSON from this file instead of the API"),
):
    """Save repos starred by the specified (or authenticated) username"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    if load:
        stars = json.load(open(load))
    else:
        stars = utils.fetch_all_starred(username, token)

    # Which user are we talking about here?
    if username:
        user = utils.fetch_user(username, token)
    else:
        user = utils.fetch_user(token=token)

    utils.save_stars(db, user, stars)
    utils.ensure_db_shape(db)


@app.command()
def stargazers(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repos: List[str] = typer.Argument(..., help="Repositories to fetch stargazers for"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
):
    """Fetch the users that have starred the specified repositories"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    for repo in repos:
        full_repo = utils.fetch_repo(repo, token=token)
        repo_id = utils.save_repo(db, full_repo)
        stargazers_data = utils.fetch_stargazers(repo, token)
        utils.save_stargazers(db, repo_id, stargazers_data)
    utils.ensure_db_shape(db)


@app.command()
def repos(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    usernames: Optional[List[str]] = typer.Argument(None, help="GitHub usernames or organizations"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
    repo: Optional[List[str]] = typer.Option(None, "-r", "--repo", help="Just fetch these repos"),
    load: Optional[str] = typer.Option(None, help="Load repos JSON from this file instead of the API"),
    readme: bool = typer.Option(False, help="Fetch README into 'readme' column"),
    readme_html: bool = typer.Option(False, "--readme-html", help="Fetch HTML rendered README into 'readme_html' column"),
):
    """Save repos owned by the specified (or authenticated) username or organization"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    if load:
        for loaded_repo in json.load(open(load)):
            utils.save_repo(db, loaded_repo)
    else:
        if repo:
            # Just these repos
            for full_name in repo:
                repo_id = utils.save_repo(db, utils.fetch_repo(full_name, token))
                _repo_readme(db, token, repo_id, full_name, readme, readme_html)
        else:
            if not usernames:
                usernames = [None]
            for username in usernames:
                for repo_item in utils.fetch_all_repos(username, token):
                    repo_id = utils.save_repo(db, repo_item)
                    _repo_readme(
                        db, token, repo_id, repo_item["full_name"], readme, readme_html
                    )
    utils.ensure_db_shape(db)


def _repo_readme(db, token, repo_id, full_name, readme, readme_html):
    if readme:
        readme = utils.fetch_readme(token, full_name)
        db["repos"].update(repo_id, {"readme": readme}, alter=True)
    if readme_html:
        readme_html = utils.fetch_readme(token, full_name, html=True)
        db["repos"].update(repo_id, {"readme_html": readme_html}, alter=True)


@app.command()
def releases(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repos: List[str] = typer.Argument(..., help="Repositories to fetch releases for"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
):
    """Save releases for the specified repos"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    first = True
    for repo in repos:
        if not first:
            time.sleep(1)
        first = False
        repo_full = utils.fetch_repo(repo, token)
        utils.save_repo(db, repo_full)
        releases_data = utils.fetch_releases(repo, token)
        utils.save_releases(db, releases_data, repo_full["id"])
    utils.ensure_db_shape(db)


@app.command()
def tags(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repos: List[str] = typer.Argument(..., help="Repositories to fetch tags for"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
):
    """Save tags for the specified repos"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    first = True
    for repo in repos:
        if not first:
            time.sleep(1)
        first = False
        repo_full = utils.fetch_repo(repo, token)
        utils.save_repo(db, repo_full)
        tags_data = utils.fetch_tags(repo, token)
        utils.save_tags(db, tags_data, repo_full["id"])
    utils.ensure_db_shape(db)


@app.command()
def contributors(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repos: List[str] = typer.Argument(..., help="Repositories to fetch contributors for"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
):
    """Save contributors for the specified repos"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    for repo in repos:
        repo_full = utils.fetch_repo(repo, token)
        utils.save_repo(db, repo_full)
        contributors_data = utils.fetch_contributors(repo, token)
        utils.save_contributors(db, contributors_data, repo_full["id"])
        time.sleep(1)
    utils.ensure_db_shape(db)


@app.command()
def commits(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repos: List[str] = typer.Argument(..., help="Repositories to fetch commits for"),
    all: bool = typer.Option(False, "--all", help="Load all commits (not just those that have not yet been saved)"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
):
    """Save commits for the specified repos"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)

    def stop_when(commit):
        try:
            db["commits"].get(commit["sha"])
            return True
        except sqlite_utils.db.NotFoundError:
            return False

    if all:
        stop_when = None

    for repo in repos:
        repo_full = utils.fetch_repo(repo, token)
        utils.save_repo(db, repo_full)

        commits_data = utils.fetch_commits(repo, token, stop_when)
        utils.save_commits(db, commits_data, repo_full["id"])
        time.sleep(1)

    utils.ensure_db_shape(db)


@app.command(name="scrape-dependents")
def scrape_dependents(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repos: List[str] = typer.Argument(..., help="Repositories to scrape dependents for"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Verbose output"),
):
    """Scrape dependents for specified repos"""
    try:
        import bs4
    except ImportError:
        typer.echo("Error: Optional dependency bs4 is needed for this command", err=True)
        raise typer.Exit(code=1)
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)

    for repo in repos:
        repo_full = utils.fetch_repo(repo, token)
        utils.save_repo(db, repo_full)

        for dependent_repo in utils.scrape_dependents(repo, verbose):
            # Don't fetch repo details if it's already in our DB
            existing = list(db["repos"].rows_where("full_name = ?", [dependent_repo]))
            dependent_id = None
            if not existing:
                dependent_full = utils.fetch_repo(dependent_repo, token)
                time.sleep(1)
                utils.save_repo(db, dependent_full)
                dependent_id = dependent_full["id"]
            else:
                dependent_id = existing[0]["id"]
            # Only insert if it isn't already there:
            if not db["dependents"].exists() or not list(
                db["dependents"].rows_where(
                    "repo = ? and dependent = ?", [repo_full["id"], dependent_id]
                )
            ):
                db["dependents"].insert(
                    {
                        "repo": repo_full["id"],
                        "dependent": dependent_id,
                        "first_seen_utc": datetime.datetime.utcnow().isoformat(),
                    },
                    pk=("repo", "dependent"),
                    foreign_keys=(
                        ("repo", "repos", "id"),
                        ("dependent", "repos", "id"),
                    ),
                )

    utils.ensure_db_shape(db)


@app.command()
def emojis(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
    fetch: bool = typer.Option(False, "-f", "--fetch", help="Fetch the image data into a BLOB column"),
):
    """Fetch GitHub supported emojis"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    table = db.table("emojis", pk="name")
    table.upsert_all(utils.fetch_emojis(token))
    if fetch:
        # Ensure table has 'image' column
        if "image" not in table.columns_dict:
            table.add_column("image", bytes)
        rows = list(table.rows_where("image is null"))
        with typer.progressbar(
            rows,
            label="Fetching emoji images",
        ) as progress:
            for emoji in progress:
                table.update(emoji["name"], {"image": utils.fetch_image(emoji["url"])})


@app.command()
def get(
    url: str = typer.Argument(..., help="URL to fetch"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
    paginate: bool = typer.Option(False, help="Paginate through all results"),
    nl: bool = typer.Option(False, help="Output newline-delimited JSON"),
    accept: Optional[str] = typer.Option(None, help="Accept header to send, e.g. application/vnd.github.VERSION.html"),
):
    """Make an authenticated HTTP GET against the specified URL"""
    token = load_token(auth)
    first = True
    should_output_closing_brace = not nl
    while url:
        response = utils.get(url, token, accept=accept)
        if "html" in (response.headers.get("content-type") or ""):
            typer.echo(response.text)
            return
        items = response.json()
        if isinstance(items, dict):
            if nl:
                typer.echo(json.dumps(items))
            else:
                typer.echo(json.dumps(items, indent=4))
            should_output_closing_brace = False
            break
        if first and not nl:
            typer.echo("[")
        for item in items:
            if not first and not nl:
                typer.echo(",")
            first = False
            if not nl:
                to_dump = json.dumps(item, indent=4)
                typer.echo(textwrap.indent(to_dump, "    "), nl=False)
            else:
                typer.echo(json.dumps(item))
        if paginate:
            url = response.links.get("next", {}).get("url")
        else:
            url = None
    if should_output_closing_brace:
        typer.echo("\n]")


@app.command()
def workflows(
    db_path: str = typer.Argument(..., help="Path to SQLite database"),
    repos: List[str] = typer.Argument(..., help="Repositories to fetch workflows for"),
    auth: str = typer.Option("auth.json", "-a", "--auth", help="Path to auth.json token file"),
):
    """Fetch details of GitHub Actions workflows for the specified repositories"""
    db = sqlite_utils.Database(db_path)
    token = load_token(auth)
    for repo in repos:
        full_repo = utils.fetch_repo(repo, token=token)
        repo_id = utils.save_repo(db, full_repo)
        workflows_data = utils.fetch_workflows(token, full_repo["full_name"])
        for filename, content in workflows_data.items():
            utils.save_workflow(db, repo_id, filename, content)
    utils.ensure_db_shape(db)


def load_token(auth):
    try:
        token = json.load(open(auth))["github_personal_token"]
    except (KeyError, FileNotFoundError):
        token = None
    if token is None:
        # Fallback to GITHUB_TOKEN environment variable
        token = os.environ.get("GITHUB_TOKEN") or None
    return token
