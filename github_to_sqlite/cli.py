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
from dataclasses import dataclass

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from github_to_sqlite import utils
from github_to_sqlite import __version__

app = typer.Typer(help="Save data from GitHub to a SQLite database")

# Reusable option types using Annotated
DbPath = Annotated[str, typer.Argument(help="Path to SQLite database")]
AuthFile = Annotated[str, typer.Option("-a", "--auth", help="Path to auth.json token file")]
RepoArg = Annotated[str, typer.Argument(help="Repository (e.g. simonw/datasette)")]
ReposList = Annotated[List[str], typer.Argument(help="Repositories")]


@dataclass
class AppState:
    """Application state shared across commands via Context."""
    db: Optional[sqlite_utils.Database] = None
    token: Optional[str] = None
    auth_file: str = "auth.json"


def version_callback(value: bool):
    if value:
        typer.echo(f"github-to-sqlite, version {__version__}")
        raise typer.Exit()


def load_token(auth: str) -> Optional[str]:
    """Load GitHub token from auth file or environment variable."""
    token = None
    try:
        token = json.load(open(auth)).get("github_personal_token")
    except FileNotFoundError:
        pass
    return token or os.environ.get("GITHUB_TOKEN")


def get_db(db_path: str) -> sqlite_utils.Database:
    """Create and return a Database instance."""
    return sqlite_utils.Database(db_path)


def finalize_db(db: sqlite_utils.Database):
    """Run final database shape operations."""
    utils.ensure_db_shape(db)


@app.callback()
def cli(
    ctx: typer.Context,
    db_path: Annotated[Optional[str], typer.Option("--db", help="Path to SQLite database")] = None,
    auth: Annotated[str, typer.Option("-a", "--auth", help="Path to auth.json token file")] = "auth.json",
    version: Optional[bool] = typer.Option(
        None, "--version", callback=version_callback, is_eager=True, help="Show version and exit"
    ),
):
    """Save data from GitHub to a SQLite database"""
    # Initialize AppState with db and token
    db = get_db(db_path) if db_path else None
    token = load_token(auth)
    ctx.obj = AppState(db=db, token=token, auth_file=auth)


@app.command()
def auth(
    auth_file: Annotated[str, typer.Option(
        "-a", "--auth", help="Path to save tokens to"
    )] = "auth.json",
):
    """Save authentication credentials to a JSON file"""
    typer.echo("Create a GitHub personal user token and paste it here:")
    typer.echo()
    personal_token = typer.prompt("Personal token", hide_input=True)
    
    auth_path = pathlib.Path(auth_file)
    auth_data = json.loads(auth_path.read_text()) if auth_path.exists() else {}
    auth_data["github_personal_token"] = personal_token
    auth_path.write_text(json.dumps(auth_data, indent=4) + "\n")
    typer.echo(f"Token saved to {auth_file}")


@app.command()
def issues(
    ctx: typer.Context,
    repo: RepoArg,
    issue: Annotated[Optional[List[int]], typer.Option(help="Just pull these issue numbers")] = None,
    load: Annotated[Optional[str], typer.Option(help="Load issues JSON from file instead of API")] = None,
):
    """Save issues for a specified repository, e.g. simonw/datasette"""
    repo_full = utils.fetch_repo(repo, ctx.obj.token)
    utils.save_repo(ctx.obj.db, repo_full)
    
    issues_data = (
        json.load(open(load)) if load
        else list(utils.fetch_issues(repo, ctx.obj.token, tuple(issue or ())))
    )
    
    utils.save_issues(ctx.obj.db, issues_data, repo_full)
    finalize_db(ctx.obj.db)


@app.command(name="pull-requests")
def pull_requests(
    ctx: typer.Context,
    repo: Annotated[Optional[str], typer.Argument(help="Repository (e.g. simonw/datasette)")] = None,
    pull_request: Annotated[Optional[List[int]], typer.Option(help="Just pull these pull-request numbers")] = None,
    load: Annotated[Optional[str], typer.Option(help="Load pull-requests JSON from file instead of API")] = None,
    org: Annotated[Optional[List[str]], typer.Option(help="Fetch all pull requests from this GitHub organization")] = None,
    pr_state: Annotated[Optional[str], typer.Option("--state", help="Only fetch pull requests in this state")] = None,
    search: Annotated[Optional[str], typer.Option(help="Find pull requests with a search query")] = None,
):
    """Save pull_requests for a specified repository, e.g. simonw/datasette"""
    pull_request_ids = tuple(pull_request or ())
    orgs = org or ()
    
    if load:
        repo_full = utils.fetch_repo(repo, ctx.obj.token)
        utils.save_repo(ctx.obj.db, repo_full)
        utils.save_pull_requests(ctx.obj.db, json.load(open(load)), repo_full)
    elif search:
        _save_searched_prs(ctx.obj.db, ctx.obj.token, search)
    else:
        repos = (
            itertools.chain.from_iterable(
                utils.fetch_all_repos(token=ctx.obj.token, org=org_name) for org_name in orgs
            ) if orgs else [utils.fetch_repo(repo, ctx.obj.token)]
        )
        for repo_full in repos:
            utils.save_repo(ctx.obj.db, repo_full)
            prs = utils.fetch_pull_requests(repo_full["full_name"], pr_state, ctx.obj.token, pull_request_ids)
            utils.save_pull_requests(ctx.obj.db, prs, repo_full)
    
    finalize_db(ctx.obj.db)


def _save_searched_prs(db: sqlite_utils.Database, token: Optional[str], search: str):
    """Helper to save PRs from search results."""
    repos_cache = {}
    for pr in utils.fetch_searched_pulls_or_issues(f"{search} is:pr", token):
        pr_repo_url = pr["repository_url"]
        if pr_repo_url not in repos_cache:
            repo_full = utils.fetch_repo(url=pr_repo_url, token=token)
            utils.save_repo(db, repo_full)
            repos_cache[pr_repo_url] = repo_full
        utils.save_pull_requests(db, [pr], repos_cache[pr_repo_url])


@app.command(name="issue-comments")
def issue_comments(
    ctx: typer.Context,
    repo: RepoArg,
    issue: Annotated[Optional[str], typer.Option(help="Just pull comments for this issue")] = None,
):
    """Retrieve issue comments for a specific repository"""
    for comment in utils.fetch_issue_comments(repo, ctx.obj.token, issue):
        utils.save_issue_comment(ctx.obj.db, comment)
    
    finalize_db(ctx.obj.db)


@app.command()
def starred(
    ctx: typer.Context,
    username: Annotated[Optional[str], typer.Argument(help="GitHub username")] = None,
    load: Annotated[Optional[str], typer.Option(help="Load starred JSON from file instead of API")] = None,
):
    """Save repos starred by the specified (or authenticated) username"""
    stars = json.load(open(load)) if load else utils.fetch_all_starred(username, ctx.obj.token)
    user = utils.fetch_user(username, ctx.obj.token) if username else utils.fetch_user(token=ctx.obj.token)
    
    utils.save_stars(ctx.obj.db, user, stars)
    finalize_db(ctx.obj.db)


@app.command()
def stargazers(
    ctx: typer.Context,
    repos: ReposList,
):
    """Fetch the users that have starred the specified repositories"""
    for repo in repos:
        full_repo = utils.fetch_repo(repo, token=ctx.obj.token)
        repo_id = utils.save_repo(ctx.obj.db, full_repo)
        utils.save_stargazers(ctx.obj.db, repo_id, utils.fetch_stargazers(repo, ctx.obj.token))
    
    finalize_db(ctx.obj.db)


@app.command()
def repos(
    ctx: typer.Context,
    usernames: Annotated[Optional[List[str]], typer.Argument(help="GitHub usernames or organizations")] = None,
    repo: Annotated[Optional[List[str]], typer.Option("-r", "--repo", help="Just fetch these repos")] = None,
    load: Annotated[Optional[str], typer.Option(help="Load repos JSON from file instead of API")] = None,
    readme: Annotated[bool, typer.Option(help="Fetch README into 'readme' column")] = False,
    readme_html: Annotated[bool, typer.Option("--readme-html", help="Fetch HTML rendered README into 'readme_html' column")] = False,
):
    """Save repos owned by the specified (or authenticated) username or organization"""
    if load:
        for loaded_repo in json.load(open(load)):
            utils.save_repo(ctx.obj.db, loaded_repo)
    elif repo:
        for full_name in repo:
            repo_id = utils.save_repo(ctx.obj.db, utils.fetch_repo(full_name, ctx.obj.token))
            _save_repo_readme(ctx.obj.db, ctx.obj.token, repo_id, full_name, readme, readme_html)
    else:
        for username in usernames or [None]:
            for repo_item in utils.fetch_all_repos(username, ctx.obj.token):
                repo_id = utils.save_repo(ctx.obj.db, repo_item)
                _save_repo_readme(ctx.obj.db, ctx.obj.token, repo_id, repo_item["full_name"], readme, readme_html)
    
    finalize_db(ctx.obj.db)


def _save_repo_readme(db: sqlite_utils.Database, token: Optional[str], repo_id: int, 
                      full_name: str, readme: bool, readme_html: bool):
    """Helper to fetch and save README content."""
    if readme:
        content = utils.fetch_readme(token, full_name)
        db["repos"].update(repo_id, {"readme": content}, alter=True)
    if readme_html:
        content = utils.fetch_readme(token, full_name, html=True)
        db["repos"].update(repo_id, {"readme_html": content}, alter=True)


@app.command()
def releases(
    ctx: typer.Context,
    repos: ReposList,
):
    """Save releases for the specified repos"""
    for i, repo in enumerate(repos):
        if i > 0:
            time.sleep(1)
        repo_full = utils.fetch_repo(repo, ctx.obj.token)
        utils.save_repo(ctx.obj.db, repo_full)
        utils.save_releases(ctx.obj.db, utils.fetch_releases(repo, ctx.obj.token), repo_full["id"])
    
    finalize_db(ctx.obj.db)


@app.command()
def tags(
    ctx: typer.Context,
    repos: ReposList,
):
    """Save tags for the specified repos"""
    for i, repo in enumerate(repos):
        if i > 0:
            time.sleep(1)
        repo_full = utils.fetch_repo(repo, ctx.obj.token)
        utils.save_repo(ctx.obj.db, repo_full)
        utils.save_tags(ctx.obj.db, utils.fetch_tags(repo, ctx.obj.token), repo_full["id"])
    
    finalize_db(ctx.obj.db)


@app.command()
def contributors(
    ctx: typer.Context,
    repos: ReposList,
):
    """Save contributors for the specified repos"""
    for repo in repos:
        repo_full = utils.fetch_repo(repo, ctx.obj.token)
        utils.save_repo(ctx.obj.db, repo_full)
        utils.save_contributors(ctx.obj.db, utils.fetch_contributors(repo, ctx.obj.token), repo_full["id"])
        time.sleep(1)
    
    finalize_db(ctx.obj.db)


@app.command()
def commits(
    ctx: typer.Context,
    repos: ReposList,
    all: Annotated[bool, typer.Option("--all", help="Load all commits (not just new ones)")] = False,
):
    """Save commits for the specified repos"""
    stop_when = None if all else _make_stop_when(ctx.obj.db)
    
    for repo in repos:
        repo_full = utils.fetch_repo(repo, ctx.obj.token)
        utils.save_repo(ctx.obj.db, repo_full)
        utils.save_commits(ctx.obj.db, utils.fetch_commits(repo, ctx.obj.token, stop_when), repo_full["id"])
        time.sleep(1)
    
    finalize_db(ctx.obj.db)


def _make_stop_when(db: sqlite_utils.Database):
    """Create a stop_when function for incremental commit fetching."""
    def stop_when(commit):
        try:
            db["commits"].get(commit["sha"])
            return True
        except sqlite_utils.db.NotFoundError:
            return False
    return stop_when


@app.command(name="scrape-dependents")
def scrape_dependents(
    ctx: typer.Context,
    repos: ReposList,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Verbose output")] = False,
):
    """Scrape dependents for specified repos"""
    try:
        import bs4  # noqa: F401
    except ImportError:
        typer.echo("Error: Optional dependency bs4 is needed for this command", err=True)
        raise typer.Exit(code=1)
    
    for repo in repos:
        repo_full = utils.fetch_repo(repo, ctx.obj.token)
        utils.save_repo(ctx.obj.db, repo_full)
        
        for dependent_repo in utils.scrape_dependents(repo, verbose):
            dependent_id = _get_or_fetch_repo_id(ctx.obj.db, ctx.obj.token, dependent_repo)
            _insert_dependent_if_new(ctx.obj.db, repo_full["id"], dependent_id)
    
    finalize_db(ctx.obj.db)


def _get_or_fetch_repo_id(db: sqlite_utils.Database, token: Optional[str], full_name: str) -> int:
    """Get repo ID from DB or fetch and save it."""
    existing = list(db["repos"].rows_where("full_name = ?", [full_name]))
    if existing:
        return existing[0]["id"]
    
    time.sleep(1)
    repo_full = utils.fetch_repo(full_name, token)
    utils.save_repo(db, repo_full)
    return repo_full["id"]


def _insert_dependent_if_new(db: sqlite_utils.Database, repo_id: int, dependent_id: int):
    """Insert dependent relationship if it doesn't exist."""
    if db["dependents"].exists():
        existing = list(db["dependents"].rows_where(
            "repo = ? and dependent = ?", [repo_id, dependent_id]
        ))
        if existing:
            return
    
    db["dependents"].insert(
        {
            "repo": repo_id,
            "dependent": dependent_id,
            "first_seen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        pk=("repo", "dependent"),
        foreign_keys=(("repo", "repos", "id"), ("dependent", "repos", "id")),
    )


@app.command()
def emojis(
    ctx: typer.Context,
    fetch: Annotated[bool, typer.Option("-f", "--fetch", help="Fetch the image data into a BLOB column")] = False,
):
    """Fetch GitHub supported emojis"""
    table = ctx.obj.db.table("emojis", pk="name")
    table.upsert_all(utils.fetch_emojis(ctx.obj.token))
    
    if fetch:
        if "image" not in table.columns_dict:
            table.add_column("image", bytes)
        
        rows = list(table.rows_where("image is null"))
        with typer.progressbar(rows, label="Fetching emoji images") as progress:
            for emoji in progress:
                table.update(emoji["name"], {"image": utils.fetch_image(emoji["url"])})


@app.command()
def get(
    ctx: typer.Context,
    url: Annotated[str, typer.Argument(help="URL to fetch")],
    paginate: Annotated[bool, typer.Option(help="Paginate through all results")] = False,
    nl: Annotated[bool, typer.Option(help="Output newline-delimited JSON")] = False,
    accept: Annotated[Optional[str], typer.Option(help="Accept header (e.g. application/vnd.github.VERSION.html)")] = None,
):
    """Make an authenticated HTTP GET against the specified URL"""
    token = ctx.obj.token
    
    first = True
    should_close_array = not nl
    
    while url:
        response = utils.get(url, token, accept=accept)
        
        # Handle HTML responses
        if "html" in (response.headers.get("content-type") or ""):
            typer.echo(response.text)
            return
        
        items = response.json()
        
        # Handle dict responses
        if isinstance(items, dict):
            typer.echo(json.dumps(items, indent=4 if not nl else None))
            should_close_array = False
            break
        
        # Handle array responses
        if first and not nl:
            typer.echo("[")
        
        for item in items:
            if not first and not nl:
                typer.echo(",")
            first = False
            
            output = json.dumps(item, indent=4 if not nl else None)
            typer.echo(textwrap.indent(output, "    ") if not nl else output, nl=nl)
        
        url = response.links.get("next", {}).get("url") if paginate else None
    
    if should_close_array:
        typer.echo("\n]")


@app.command()
def workflows(
    ctx: typer.Context,
    repos: ReposList,
):
    """Fetch details of GitHub Actions workflows for the specified repositories"""
    for repo in repos:
        full_repo = utils.fetch_repo(repo, token=ctx.obj.token)
        repo_id = utils.save_repo(ctx.obj.db, full_repo)
        
        for filename, content in utils.fetch_workflows(ctx.obj.token, full_repo["full_name"]).items():
            utils.save_workflow(ctx.obj.db, repo_id, filename, content)
    
    finalize_db(ctx.obj.db)
