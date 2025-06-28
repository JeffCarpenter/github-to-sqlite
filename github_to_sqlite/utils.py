import base64
import sys
import os
import subprocess
import shutil
import requests
import re
import time
import urllib.parse
import yaml
import sqlite_utils
import pathlib
import sqlite3
import json
from typing import Optional, cast

from . import config


from urllib3 import Retry
from requests.adapters import HTTPAdapter


FTS_CONFIG = {
    # table: columns
    "commits": ["message"],
    "issue_comments": ["body"],
    "issues": ["title", "body"],
    "pull_requests": ["title", "body"],
    "labels": ["name", "description"],
    "licenses": ["name"],
    "milestones": ["title", "description"],
    "releases": ["name", "body"],
    "repos": ["name", "description"],
    "users": ["login", "name"],
}

VIEWS = {
    # Name: (required_tables, SQL)
    "dependent_repos": (
        {"repos", "dependents"},
        """select
  repos.full_name as repo,
  'https://github.com/' || dependent_repos.full_name as dependent,
  dependent_repos.created_at as dependent_created,
  dependent_repos.updated_at as dependent_updated,
  dependent_repos.stargazers_count as dependent_stars,
  dependent_repos.watchers_count as dependent_watchers
from
  dependents
  join repos as dependent_repos on dependents.dependent = dependent_repos.id
  join repos on dependents.repo = repos.id
order by
  dependent_repos.created_at desc""",
    ),
    "repos_starred": (
        {"stars", "repos", "users"},
        """select
  stars.starred_at,
  starring_user.login as starred_by,
  repos.*
from
  repos
  join stars on repos.id = stars.repo
  join users as starring_user on stars.user = starring_user.id
  join users on repos.owner = users.id
order by
  starred_at desc""",
    ),
    "recent_releases": (
        {"repos", "releases"},
        """select
  repos.rowid as rowid,
  repos.html_url as repo,
  releases.html_url as release,
  substr(releases.published_at, 0, 11) as date,
  releases.body as body_markdown,
  releases.published_at,
  coalesce(repos.topics, '[]') as topics
from
  releases
  join repos on repos.id = releases.repo
order by
  releases.published_at desc""",
    ),
}

FOREIGN_KEYS = [
    ("repos", "license", "licenses", "key"),
]


class GitHubError(Exception):
    def __init__(self, message, status_code, headers=None):
        self.message = message
        self.status_code = status_code
        self.headers = headers

    @classmethod
    def from_response(cls, response):
        message = response.json()["message"]
        if "git repository is empty" in message.lower():
            cls = GitHubRepositoryEmpty
        return cls(message, response.status_code, response.headers)


class GitHubRepositoryEmpty(GitHubError):
    pass


def save_issues(db, issues, repo):
    if "milestones" not in db.table_names():
        if "users" not in db.table_names():
            # So we can define the foreign key from milestones:
            db["users"].create({"id": int}, pk="id")
        db["milestones"].create(
            {"id": int, "title": str, "description": str, "creator": int, "repo": int},
            pk="id",
            foreign_keys=(("repo", "repos", "id"), ("creator", "users", "id")),
        )
    for original in issues:
        # Ignore all of the _url fields
        issue = {
            key: value for key, value in original.items() if not key.endswith("url")
        }
        # Add repo key
        issue["repo"] = repo["id"]
        # Pull request can be flattened to just their URL
        if issue.get("pull_request"):
            issue["pull_request"] = issue["pull_request"]["url"].split(
                "https://api.github.com/repos/"
            )[1]
        # Extract user
        issue["user"] = save_user(db, issue["user"])
        labels = issue.pop("labels")
        # Extract milestone
        if issue["milestone"]:
            issue["milestone"] = save_milestone(db, issue["milestone"], repo["id"])
        # For the moment we ignore the assignees=[] array but we DO turn assignee
        # singular into a foreign key reference
        issue.pop("assignees", None)
        if issue["assignee"]:
            issue["assignee"] = save_user(db, issue["assignee"])
        # Add a type field to distinguish issues from pulls
        issue["type"] = "pull" if issue.get("pull_request") else "issue"
        # Insert record
        table = db["issues"].insert(
            issue,
            pk="id",
            foreign_keys=[
                ("user", "users", "id"),
                ("assignee", "users", "id"),
                ("milestone", "milestones", "id"),
                ("repo", "repos", "id"),
            ],
            alter=True,
            replace=True,
            columns={
                "user": int,
                "assignee": int,
                "milestone": int,
                "repo": int,
                "title": str,
                "body": str,
            },
        )
        # m2m for labels
        for label in labels:
            table.m2m("labels", label, pk="id")


def save_pull_requests(db, pull_requests, repo):
    if "milestones" not in db.table_names():
        if "users" not in db.table_names():
            # So we can define the foreign key from milestones:
            db["users"].create({"id": int}, pk="id")
        db["milestones"].create(
            {"id": int, "title": str, "description": str, "creator": int, "repo": int},
            pk="id",
            foreign_keys=(("repo", "repos", "id"), ("creator", "users", "id")),
        )
    for original in pull_requests:
        # Ignore all of the _url fields
        pull_request = {
            key: value for key, value in original.items() if not key.endswith("url")
        }
        # Add repo key
        pull_request["repo"] = repo["id"]
        # Pull request _links can be flattened to just their URL
        if "_links" in pull_request:
            pull_request["url"] = pull_request["_links"]["html"]["href"]
            pull_request.pop("_links")
        else:
            pull_request["url"] = pull_request["pull_request"]["html_url"]
        # Extract user
        pull_request["user"] = save_user(db, pull_request["user"])
        labels = pull_request.pop("labels")
        # Extract merged_by, if it exists
        if pull_request.get("merged_by"):
            pull_request["merged_by"] = save_user(db, pull_request["merged_by"])
        # Head sha
        if "head" in pull_request:
            pull_request["head"] = pull_request["head"]["sha"]
            pull_request["base"] = pull_request["base"]["sha"]
        # Extract milestone
        if pull_request["milestone"]:
            pull_request["milestone"] = save_milestone(
                db, pull_request["milestone"], repo["id"]
            )
        # For the moment we ignore the assignees=[] array but we DO turn assignee
        # singular into a foreign key reference
        pull_request.pop("assignees", None)
        if original["assignee"]:
            pull_request["assignee"] = save_user(db, pull_request["assignee"])
        pull_request.pop("active_lock_reason")
        # ignore requested_reviewers and requested_teams
        pull_request.pop("requested_reviewers", None)
        pull_request.pop("requested_teams", None)
        # Insert record
        table = db["pull_requests"].insert(
            pull_request,
            pk="id",
            foreign_keys=[
                ("user", "users", "id"),
                ("merged_by", "users", "id"),
                ("assignee", "users", "id"),
                ("milestone", "milestones", "id"),
                ("repo", "repos", "id"),
            ],
            alter=True,
            replace=True,
            columns={
                "user": int,
                "assignee": int,
                "milestone": int,
                "repo": int,
                "title": str,
                "body": str,
                "merged_by": int,
            },
        )
        # m2m for labels
        for label in labels:
            table.m2m("labels", label, pk="id")


def save_user(db, user):
    # Under some conditions, GitHub caches removed repositories with  
    # stars and ends up leaving dangling `None` user references.
    if user is None:
        return None
    
    # Remove all url fields except avatar_url and html_url
    to_save = {
        key: value
        for key, value in user.items()
        if (key in ("avatar_url", "html_url") or not key.endswith("url"))
    }
    # If this user was nested in repo they will be missing several fields
    # so fill in 'name' from 'login' so Datasette foreign keys display
    if to_save.get("name") is None:
        to_save["name"] = to_save["login"]
    return db["users"].upsert(to_save, pk="id", alter=True).last_pk


def save_milestone(db, milestone, repo_id):
    milestone = dict(milestone)
    milestone["creator"] = save_user(db, milestone["creator"])
    milestone["repo"] = repo_id
    milestone.pop("labels_url", None)
    milestone.pop("url", None)
    return (
        db["milestones"]
        .insert(
            milestone,
            pk="id",
            foreign_keys=[("creator", "users", "id"), ("repo", "repos", "id")],
            alter=True,
            replace=True,
            columns={"creator": int, "repo": int},
        )
        .last_pk
    )


def save_issue_comment(db, comment):
    comment = dict(comment)
    comment["user"] = save_user(db, comment["user"])
    # We set up a 'issue' foreign key, but only if issue is in the DB
    comment["issue"] = None
    issue_url = comment["issue_url"]
    bits = issue_url.split("/")
    user_slug, repo_slug, issue_number = bits[-4], bits[-3], bits[-1]
    # Is the issue in the DB already?
    issue_rows = list(
        db["issues"].rows_where(
            "number = :number and repo = (select id from repos where full_name = :repo)",
            {"repo": "{}/{}".format(user_slug, repo_slug), "number": issue_number},
        )
    )
    if len(issue_rows) == 1:
        comment["issue"] = issue_rows[0]["id"]
    comment.pop("url", None)
    if "url" in comment.get("reactions", {}):
        comment["reactions"].pop("url")
    last_pk = (
        db["issue_comments"]
        .insert(
            comment, pk="id", foreign_keys=("user", "issue"), alter=True, replace=True
        )
        .last_pk
    )
    return last_pk


def fetch_repo(full_name=None, token=None, url=None):
    headers = make_headers(token)
    # Get topics:
    headers["Accept"] = "application/vnd.github.mercy-preview+json"
    if url is None:
        owner, slug = full_name.split("/")
        url = "https://api.github.com/repos/{}/{}".format(owner, slug)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def save_repo(db, repo):
    assert isinstance(repo, dict), "Repo should be a dict: {}".format(repr(repo))
    # Remove all url fields except html_url
    to_save = {
        key: value
        for key, value in repo.items()
        if (key == "html_url") or not key.endswith("url")
    }
    to_save["owner"] = save_user(db, to_save["owner"])
    to_save["license"] = save_license(db, to_save["license"])
    if "organization" in to_save:
        to_save["organization"] = save_user(db, to_save["organization"])
    else:
        to_save["organization"] = None
    repo_id = (
        db["repos"]
        .insert(
            to_save,
            pk="id",
            foreign_keys=(("owner", "users", "id"), ("organization", "users", "id")),
            alter=True,
            replace=True,
            columns={
                "organization": int,
                "topics": str,
                "name": str,
                "description": str,
            },
        )
        .last_pk
    )
    return repo_id


def save_license(db, license):
    if license is None:
        return None
    return db["licenses"].insert(license, pk="key", replace=True).last_pk


def fetch_issues(repo, token=None, issue_ids=None):
    headers = make_headers(token)
    headers["accept"] = "application/vnd.github.v3+json"
    if issue_ids:
        for issue_id in issue_ids:
            url = "https://api.github.com/repos/{}/issues/{}".format(repo, issue_id)
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            yield response.json()
    else:
        url = "https://api.github.com/repos/{}/issues?state=all&filter=all".format(repo)
        for issues in paginate(url, headers):
            yield from issues


def fetch_pull_requests(repo, state=None, token=None, pull_request_ids=None):
    headers = make_headers(token)
    headers["accept"] = "application/vnd.github.v3+json"
    if pull_request_ids:
        for pull_request_id in pull_request_ids:
            url = "https://api.github.com/repos/{}/pulls/{}".format(
                repo, pull_request_id
            )
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            yield response.json()
    else:
        state = state or "all"
        url = f"https://api.github.com/repos/{repo}/pulls?state={state}"
        for pull_requests in paginate(url, headers):
            yield from pull_requests


def fetch_searched_pulls_or_issues(query, token=None):
    headers = make_headers(token)
    url = "https://api.github.com/search/issues?"
    url += urllib.parse.urlencode({"q": query})
    for pulls_or_issues in paginate(url, headers):
        yield from pulls_or_issues["items"]


def fetch_issue_comments(repo, token=None, issue=None):
    assert "/" in repo
    headers = make_headers(token)
    # Get reactions:
    headers["Accept"] = "application/vnd.github.squirrel-girl-preview"
    path = "/repos/{}/issues/comments".format(repo)
    if issue is not None:
        path = "/repos/{}/issues/{}/comments".format(repo, issue)
    url = "https://api.github.com{}".format(path)
    for comments in paginate(url, headers):
        yield from comments


def fetch_releases(repo, token=None):
    headers = make_headers(token)
    url = "https://api.github.com/repos/{}/releases".format(repo)
    for releases in paginate(url, headers):
        yield from releases


def fetch_contributors(repo, token=None):
    headers = make_headers(token)
    url = "https://api.github.com/repos/{}/contributors".format(repo)
    for contributors in paginate(url, headers):
        yield from contributors


def fetch_tags(repo, token=None):
    headers = make_headers(token)
    url = "https://api.github.com/repos/{}/tags".format(repo)
    for tags in paginate(url, headers):
        yield from tags


def fetch_commits(repo, token=None, stop_when=None):
    if stop_when is None:
        def stop_when(commit):
            return False
    headers = make_headers(token)
    url = "https://api.github.com/repos/{}/commits".format(repo)
    try:
        for commits in paginate(url, headers):
            for commit in commits:
                if stop_when(commit):
                    return
                else:
                    yield commit
    except GitHubRepositoryEmpty:
        return


def fetch_all_starred(username=None, token=None):
    assert username or token, "Must provide username= or token= or both"
    headers = make_headers(token)
    headers["Accept"] = "application/vnd.github.v3.star+json"
    if username:
        url = "https://api.github.com/users/{}/starred".format(username)
    else:
        url = "https://api.github.com/user/starred"
    for stars in paginate(url, headers):
        yield from stars


def fetch_stargazers(repo, token=None):
    headers = make_headers(token)
    headers["Accept"] = "application/vnd.github.v3.star+json"
    url = "https://api.github.com/repos/{}/stargazers".format(repo)
    for stargazers in paginate(url, headers):
        yield from stargazers


def fetch_all_repos(username=None, token=None, org=None):
    assert username or token or org, "Must provide username= or token= or org= or a combination"
    headers = make_headers(token)
    # Get topics for each repo:
    headers["Accept"] = "application/vnd.github.mercy-preview+json"
    if username:
        url = "https://api.github.com/users/{}/repos".format(username)
    elif org:
        url = "https://api.github.com/orgs/{}/repos".format(org)
    else:
        url = "https://api.github.com/user/repos"
    for repos in paginate(url, headers):
        yield from repos


def fetch_user(username=None, token=None):
    assert username or token, "Must provide username= or token= or both"
    headers = make_headers(token)
    if username:
        url = "https://api.github.com/users/{}".format(username)
    else:
        url = "https://api.github.com/user"
    return requests.get(url, headers=headers).json()


def paginate(url, headers=None):
    url += ("&" if "?" in url else "?") + "per_page=100"
    sess = requests.Session()
    retries = Retry(backoff_factor=0.1, raise_on_status=False, status_forcelist=[500, 502, 503, 504])
    sess.mount("https://", HTTPAdapter(max_retries=retries))

    while url:
        response = sess.get(url, headers=headers)
        # For HTTP 204 no-content this yields an empty list
        if response.status_code == 204:
            return
        data = response.json()
        if isinstance(data, dict) and data.get("message"):
            print(GitHubError.from_response(response), file=sys.stderr)
        try:
            url = response.links.get("next", {}).get("url") if response.status_code == 200 else url
        except AttributeError:
            url = None
        yield data


def make_headers(token=None):
    headers = {}
    if token is not None:
        headers["Authorization"] = "token {}".format(token)
    return headers


def save_stars(db, user, stars):
    user_id = save_user(db, user)

    for star in stars:
        starred_at = star["starred_at"]
        repo = star["repo"]
        repo_id = save_repo(db, repo)
        db["stars"].insert(
            {"user": user_id, "repo": repo_id, "starred_at": starred_at},
            pk=("user", "repo"),
            foreign_keys=("user", "repo"),
            replace=True,
        )


def save_stargazers(db, repo_id, stargazers):
    for stargazer in stargazers:
        starred_at = stargazer["starred_at"]
        user_id = save_user(db, stargazer["user"])
        db["stars"].upsert(
            {"user": user_id, "repo": repo_id, "starred_at": starred_at},
            pk=("user", "repo"),
            foreign_keys=("user", "repo"),
        )


def save_releases(db, releases, repo_id=None):
    foreign_keys = [("author", "users", "id")]
    if repo_id:
        foreign_keys.append(("repo", "repos", "id"))
    for original in releases:
        # Ignore all of the _url fields except html_url
        release = {
            key: value
            for key, value in original.items()
            if key == "html_url" or not key.endswith("url")
        }
        assets = release.pop("assets") or []
        release["repo"] = repo_id
        release["author"] = save_user(db, release["author"])
        release_id = (
            db["releases"]
            .insert(
                release, pk="id", foreign_keys=foreign_keys, alter=True, replace=True
            )
            .last_pk
        )
        # Handle assets
        for asset in assets:
            asset["uploader"] = save_user(db, asset["uploader"])
            asset["release"] = release_id

        db["assets"].upsert_all(
            assets,
            pk="id",
            foreign_keys=[
                ("uploader", "users", "id"),
                ("release", "releases", "id"),
            ],
            alter=True,
        )


def save_contributors(db, contributors, repo_id):
    contributor_rows_to_add = []
    for contributor in contributors:
        contributions = contributor.pop("contributions")
        user_id = save_user(db, contributor)
        contributor_rows_to_add.append(
            {"repo_id": repo_id, "user_id": user_id, "contributions": contributions}
        )
    db["contributors"].insert_all(
        contributor_rows_to_add,
        pk=("repo_id", "user_id"),
        foreign_keys=[("repo_id", "repos", "id"), ("user_id", "users", "id")],
        replace=True,
    )


def save_tags(db, tags, repo_id):
    if not db["tags"].exists():
        db["tags"].create(
            {
                "repo": int,
                "name": str,
                "sha": str,
            },
            pk=("repo", "name"),
            foreign_keys=[("repo", "repos", "id")],
        )

    db["tags"].insert_all(
        (
            {
                "repo": repo_id,
                "name": tag["name"],
                "sha": tag["commit"]["sha"],
            }
            for tag in tags
        ),
        replace=True,
    )


def save_commits(db, commits, repo_id=None):
    foreign_keys = [
        ("author", "users", "id"),
        ("committer", "users", "id"),
        ("raw_author", "raw_authors", "id"),
        ("raw_committer", "raw_authors", "id"),
        ("repo", "repos", "id"),
    ]

    if not db["raw_authors"].exists():
        db["raw_authors"].create(
            {
                "id": str,
                "name": str,
                "email": str,
            },
            pk="id",
        )

    if not db["commits"].exists():
        # We explicitly create the table because otherwise we may create it
        # with incorrect column types, since author/committer can be null
        db["commits"].create(
            {
                "sha": str,
                "message": str,
                "author_date": str,
                "committer_date": str,
                "raw_author": str,
                "raw_committer": str,
                "repo": int,
                "author": int,
                "committer": int,
            },
            pk="sha",
            foreign_keys=foreign_keys,
        )

    for commit in commits:
        commit_to_insert = {
            "sha": commit["sha"],
            "message": commit["commit"]["message"],
            "author_date": commit["commit"]["author"]["date"],
            "committer_date": commit["commit"]["committer"]["date"],
            "raw_author": save_commit_author(db, commit["commit"]["author"]),
            "raw_committer": save_commit_author(db, commit["commit"]["committer"]),
        }
        commit_to_insert["repo"] = repo_id
        commit_to_insert["author"] = (
            save_user(db, commit["author"]) if commit["author"] else None
        )
        commit_to_insert["committer"] = (
            save_user(db, commit["committer"]) if commit["committer"] else None
        )
        db["commits"].insert(
            commit_to_insert,
            alter=True,
            replace=True,
        )


def save_commit_author(db, raw_author):
    name = raw_author.get("name")
    email = raw_author.get("email")
    return (
        db["raw_authors"]
        .insert(
            {
                "name": name,
                "email": email,
            },
            hash_id="id",
            replace=True,
        )
        .last_pk
    )


def ensure_foreign_keys(db):
    for expected_foreign_key in FOREIGN_KEYS:
        table, column, table2, column2 = expected_foreign_key
        if (
            expected_foreign_key not in db[table].foreign_keys
            and
            # Ensure all tables and columns exist
            db[table].exists()
            and db[table2].exists()
            and column in db[table].columns_dict
            and column2 in db[table2].columns_dict
        ):
            db[table].add_foreign_key(column, table2, column2)


_SQLITE_VEC_LOADED: bool | None = None


def _create_table_if_missing(
    db: sqlite_utils.Database,
    tables: set[str],
    name: str,
    columns: dict[str, type],
    pk: str | tuple[str, ...],
    foreign_keys: list[tuple[str, str, str]] | None = None,
) -> None:
    """Create *name* if it doesn't exist in *tables*."""
    if name not in tables:
        table = cast(sqlite_utils.db.Table, db[name])
        table.create(columns, pk=pk, foreign_keys=foreign_keys or [])


def _create_virtual_table_if_missing(db: sqlite_utils.Database, name: str, sql: str) -> None:
    """Create a virtual table using provided SQL if it does not already exist."""
    existing = set(db.table_names())
    if name not in existing:
        db.execute(sql)


def _maybe_load_sqlite_vec(db):
    """Attempt to load sqlite-vec extension, returning True if available."""
    global _SQLITE_VEC_LOADED
    if _SQLITE_VEC_LOADED is not None:
        return _SQLITE_VEC_LOADED
    try:
        import sqlite_vec
    except ImportError:
        _SQLITE_VEC_LOADED = False
        return _SQLITE_VEC_LOADED
    try:
        sqlite_vec.load(db.conn)
    except (OSError, sqlite3.DatabaseError, AttributeError):
        _SQLITE_VEC_LOADED = False
    else:
        _SQLITE_VEC_LOADED = True
    return _SQLITE_VEC_LOADED


def ensure_embedding_tables(db):
    """Create tables used for embedding storage if they do not exist."""
    using_vec = _maybe_load_sqlite_vec(db)

    tables = set(db.table_names())

    if "repo_embeddings" not in tables:
        if using_vec:
            _create_virtual_table_if_missing(
                db,
                "repo_embeddings",
                """
                create virtual table if not exists repo_embeddings using vec0(
                    repo_id int primary key,
                    title_embedding float[768],
                    description_embedding float[768],
                    readme_embedding float[768]
                )
                """,
            )
        else:
            _create_table_if_missing(
                db,
                tables,
                "repo_embeddings",
                {
                    "repo_id": int,
                    "title_embedding": bytes,
                    "description_embedding": bytes,
                    "readme_embedding": bytes,
                },
                pk="repo_id",
                foreign_keys=[("repo_id", "repos", "id")] if "repos" in tables else [],
            )

    if "readme_chunk_embeddings" not in tables:
        if using_vec:
            _create_virtual_table_if_missing(
                db,
                "readme_chunk_embeddings",
                """
                create virtual table if not exists readme_chunk_embeddings using vec0(
                    repo_id int,
                    chunk_index int,
                    chunk_text text,
                    embedding float[768]
                )
                """,
            )
            db.execute(
                "create index if not exists readme_chunk_idx on readme_chunk_embeddings(repo_id, chunk_index)"
            )
        else:
            _create_table_if_missing(
                db,
                tables,
                "readme_chunk_embeddings",
                {
                    "repo_id": int,
                    "chunk_index": int,
                    "chunk_text": str,
                    "embedding": bytes,
                },
                pk=("repo_id", "chunk_index"),
                foreign_keys=[("repo_id", "repos", "id")] if "repos" in tables else [],
            )

    _create_table_if_missing(
        db,
        tables,
        "repo_build_files",
        {"repo_id": int, "file_path": str, "metadata": str},
        pk=("repo_id", "file_path"),
        foreign_keys=[("repo_id", "repos", "id")] if "repos" in tables else [],
    )

    _create_table_if_missing(
        db,
        tables,
        "repo_metadata",
        {"repo_id": int, "language": str, "directory_tree": str},
        pk="repo_id",
        foreign_keys=[("repo_id", "repos", "id")] if "repos" in tables else [],
    )


def ensure_db_shape(db):
    "Ensure FTS is configured and expected FKS, views and (soon) indexes are present"
    # Foreign keys:
    ensure_foreign_keys(db)
    db.index_foreign_keys()

    ensure_embedding_tables(db)

    # FTS:
    existing_tables = set(db.table_names())
    for table, columns in FTS_CONFIG.items():
        if "{}_fts".format(table) in existing_tables:
            continue
        if table not in existing_tables:
            continue
        db[table].enable_fts(columns, create_triggers=True)

    # Views:
    existing_tables = set(db.table_names())
    for view, (tables, sql) in VIEWS.items():
        # Do all of the tables exist?
        if not tables.issubset(existing_tables):
            continue
        db.create_view(view, sql, replace=True)


def scrape_dependents(repo, verbose=False):
    # Optional dependency:
    from bs4 import BeautifulSoup

    url: str | None = "https://github.com/{}/network/dependents".format(repo)
    while url:
        if verbose:
            print(url)
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        repos = [
            str(a["href"]).lstrip("/")
            for a in soup.select("a[data-hovercard-type=repository]")
        ]
        if verbose:
            print(repos)
        yield from repos
        # next page?
        try:
            next_link = soup.select(".paginate-container")[0].find("a", string="Next")
        except IndexError:
            break
        if next_link is not None:
            from bs4.element import Tag

            tag = cast(Tag, next_link)
            url = cast(Optional[str], tag.get("href"))
            time.sleep(1)
        else:
            url = None


def fetch_emojis(token=None):
    headers = make_headers(token)
    response = requests.get("https://api.github.com/emojis", headers=headers)
    response.raise_for_status()
    return [{"name": key, "url": value} for key, value in response.json().items()]


def fetch_image(url):
    return requests.get(url).content


def get(url, token=None, accept=None):
    headers = make_headers(token)
    if accept:
        headers["accept"] = accept
    if url.startswith("/"):
        url = "https://api.github.com{}".format(url)
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response


def fetch_readme(token, full_name, html=False):
    headers = make_headers(token)
    if html:
        headers["accept"] = "application/vnd.github.VERSION.html"
    url = "https://api.github.com/repos/{}/readme".format(full_name)
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return None
    if html:
        return rewrite_readme_html(response.text)
    else:
        return base64.b64decode(response.json()["content"]).decode("utf-8")


_href_re = re.compile(r'\shref="#([^"]+)"')
_id_re = re.compile(r'\sid="([^"]+)"')


def rewrite_readme_html(html):
    # href="#filtering-tables" => href="#user-content-filtering-tables"
    hrefs = set(_href_re.findall(html))
    ids = _id_re.findall(html)
    for href in hrefs:
        if "user-content-{}".format(href) not in ids:
            continue
        if href.startswith("user-content-"):
            continue
        # This href should be rewritten to user-content
        html = html.replace(
            ' href="#{}"'.format(href), ' href="#user-content-{}"'.format(href)
        )
    return html


def chunk_readme(text):
    """Return a list of textual chunks for the provided README content.

    Attempts to use ``semantic_chunkers.StatisticalChunker`` if available;
    otherwise falls back to splitting on blank lines. This allows tests to run
    without the optional dependency installed.
    """

    try:
        from semantic_chunkers.chunkers import StatisticalChunker
    except ImportError:
        pass
    else:
        chunker = StatisticalChunker()
        return list(chunker.chunk(text))

    # Fallback: split on blank lines
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]


def fetch_workflows(token, full_name):
    headers = make_headers(token)
    url = "https://api.github.com/repos/{}/contents/.github/workflows".format(full_name)
    response = requests.get(url, headers=headers)
    if response.status_code == 404:
        return {}
    workflows = {}
    for item in response.json():
        name = item["name"]
        content = requests.get(item["download_url"]).text
        workflows[name] = content
    return workflows


def save_workflow(db, repo_id, filename, content):
    workflow = yaml.safe_load(content)
    jobs = workflow.pop("jobs", None) or {}
    # If there's a `True` key it was probably meant to be "on" - grr YAML
    if True in workflow:
        workflow["on"] = workflow.pop(True)
    # Replace workflow if one exists already
    existing = list(
        db["workflows"].rows_where("repo = ? and filename = ?", [repo_id, filename])
    )
    if existing:
        # Delete jobs, steps and this record
        existing_id = existing[0]["id"]
        db["steps"].delete_where(
            "job in (select id from jobs where workflow = ?)", [existing_id]
        )
        db["jobs"].delete_where("workflow = ?", [existing_id])
        db["workflows"].delete_where("id = ?", [existing_id])
    workflow_id = (
        db["workflows"]
        .insert(
            {
                **workflow,
                **{
                    "repo": repo_id,
                    "filename": filename,
                    "name": workflow.get("name", filename),
                },
            },
            pk="id",
            column_order=["id", "filename", "name"],
            alter=True,
            foreign_keys=["repo"],
        )
        .last_pk
    )
    db["workflows"].create_index(["repo", "filename"], unique=True, if_not_exists=True)
    for job_name, job_details in jobs.items():
        steps = job_details.pop("steps", None) or []
        job_id = (
            db["jobs"]
            .insert(
                {
                    **{
                        "workflow": workflow_id,
                        "name": job_name,
                        "repo": repo_id,
                    },
                    **job_details,
                },
                pk="id",
                alter=True,
                foreign_keys=["workflow", "repo"],
            )
            .last_pk
        )
        db["steps"].insert_all(
            [
                {
                    **{
                        "seq": i + 1,
                        "job": job_id,
                        "repo": repo_id,
                    },
                    **step,
                }
                for i, step in enumerate(steps)
            ],
            alter=True,
            pk="id",
            foreign_keys=["job", "repo"],
        )

# Utility to locate build definition files using fd, find or os.walk


BUILD_PATTERNS = ["pyproject.toml", "package.json", "Cargo.toml", "Gemfile"]


def _post_process_build_files(found: list[str], base: str) -> list[str]:
    """Normalize paths, filter junk and deduplicate while preserving order."""
    unique: list[str] = []
    seen = set()
    for item in found:
        if "/.git/" in item or "/node_modules/" in item:
            continue
        norm_path = os.path.normpath(item)
        if os.path.isabs(norm_path) or norm_path.startswith(os.path.normpath(base) + os.sep):
            norm = os.path.relpath(norm_path, base)
        else:
            norm = norm_path
        if norm not in seen:
            unique.append(norm)
            seen.add(norm)
    return unique

def find_build_files(path: str) -> list[str]:
    """Return a list of build definition files under *path*.

    The helper prefers the ``fd`` command if available, then falls back to
    ``find`` and finally to walking the directory tree with ``os.walk``. Paths
    are returned relative to *path*.
    """
    found: list[str] = []

    if shutil.which("fd"):
        for pattern in BUILD_PATTERNS:
            try:
                result = subprocess.run(
                    ["fd", "-HI", "-t", "f", pattern, path],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                continue
            found.extend(result.stdout.splitlines())
    elif shutil.which("find"):
        for pattern in BUILD_PATTERNS:
            try:
                result = subprocess.run(
                    ["find", path, "-name", pattern, "-type", "f"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                continue
            found.extend(result.stdout.splitlines())
    else:
        for pattern in BUILD_PATTERNS:
            for full in pathlib.Path(path).rglob(pattern):
                if full.is_file():
                    found.append(str(full))
    return _post_process_build_files(found, path)


def vector_to_blob(vec) -> bytes:
    """Return a float32 byte string for the provided vector."""
    import numpy as np

    arr = np.asarray(vec, dtype="float32")
    return arr.tobytes()


def parse_build_file(path: str) -> dict:
    """Parse a supported build file and return its contents as a dict."""
    import json
    try:
        import tomllib
    except ImportError:  # Python <3.11
        import tomli as tomllib

    try:
        if path.endswith(".json"):
            with open(path) as fp:
                return json.load(fp)
        with open(path, "rb") as fp:
            return tomllib.load(fp)
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError):
        return {}


def directory_tree(path: str) -> dict:
    """Return a simple directory tree representation for *path*."""
    tree = {}
    for root, dirs, files in os.walk(path):
        rel = os.path.relpath(root, path)
        tree[rel] = {"dirs": sorted(dirs), "files": sorted(files)}
    return tree


def generate_starred_embeddings(
    db: sqlite_utils.Database,
    token: str,
    model_name: str | None = None,
    *,
    force: bool = False,
    verbose: bool = False,
) -> None:
    """Generate embeddings for repos starred by the authenticated user."""
    from sentence_transformers import SentenceTransformer
    import numpy as np

    ensure_db_shape(db)
    using_vec = _maybe_load_sqlite_vec(db)
    if verbose:
        if using_vec:
            print("Using sqlite-vec for embedding storage")
        else:
            print("sqlite-vec extension not loaded; storing embeddings as BLOBs")

    env_model = os.environ.get("GITHUB_TO_SQLITE_MODEL")
    model_name = model_name or env_model or config.config.default_model
    embedder = SentenceTransformer(model_name)

    batch_size = 32
    for star in fetch_all_starred(token=token):
        repo = star["repo"]
        repo_id = save_repo(db, repo)

        repo_embeddings = cast(sqlite_utils.db.Table, db["repo_embeddings"])
        if not force and repo_embeddings.count_where("repo_id = ?", [repo_id]):
            if verbose:
                print(f"Skipping {repo['full_name']} (already processed)")
            continue

        title = repo.get("name") or ""
        description = repo.get("description") or ""
        readme = fetch_readme(token, repo["full_name"]) or ""
        chunks = chunk_readme(readme)

        title_vec, desc_vec = embedder.encode([title, description])
        chunk_vecs = []
        for i in range(0, len(chunks), batch_size):
            part = chunks[i : i + batch_size]
            chunk_vecs.extend(embedder.encode(list(part)))

        readme_vec = np.mean(chunk_vecs, axis=0) if chunk_vecs else np.zeros_like(
            title_vec
        )

        if using_vec:
            import sqlite_vec

            title_val = sqlite_vec.serialize_float32(list(title_vec))
            desc_val = sqlite_vec.serialize_float32(list(desc_vec))
            readme_val = sqlite_vec.serialize_float32(list(readme_vec))
        else:
            title_val = vector_to_blob(title_vec)
            desc_val = vector_to_blob(desc_vec)
            readme_val = vector_to_blob(readme_vec)

        repo_embeddings.upsert(
            {
                "repo_id": repo_id,
                "title_embedding": title_val,
                "description_embedding": desc_val,
                "readme_embedding": readme_val,
            },
            pk="repo_id",
        )

        for i, (chunk, vec) in enumerate(zip(chunks, chunk_vecs)):
            chunk_val = (
                sqlite_vec.serialize_float32(list(vec)) if using_vec else vector_to_blob(vec)
            )
            cast(sqlite_utils.db.Table, db["readme_chunk_embeddings"]).upsert(
                {
                    "repo_id": repo_id,
                    "chunk_index": i,
                    "chunk_text": chunk,
                    "embedding": chunk_val,
                },
                pk=("repo_id", "chunk_index"),
            )

        for build_path in find_build_files(repo["full_name"]):
            metadata = parse_build_file(os.path.join(repo["full_name"], build_path))
            cast(sqlite_utils.db.Table, db["repo_build_files"]).upsert(
                {
                    "repo_id": repo_id,
                    "file_path": build_path,
                    "metadata": json.dumps(metadata),
                },
                pk=("repo_id", "file_path"),
            )

        cast(sqlite_utils.db.Table, db["repo_metadata"]).upsert(
            {
                "repo_id": repo_id,
                "language": repo.get("language") or "",
                "directory_tree": json.dumps(directory_tree(repo["full_name"])),
            },
            pk="repo_id",
        )

        if verbose:
            print(f"Processed {repo['full_name']}")

