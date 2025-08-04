"""Helpers for discovering and parsing build definition files."""
from __future__ import annotations

import os
import pathlib
import subprocess
import shutil
import json
from typing import Iterable, List
import warnings


BUILD_PATTERNS = ["pyproject.toml", "package.json", "Cargo.toml", "Gemfile"]


def _post_process_build_files(found: List[str], base: str) -> List[str]:
    """Normalize paths, filter junk and deduplicate while preserving order."""
    unique: List[str] = []
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


def find_build_files(path: str, patterns: Iterable[str] | None = None) -> List[str]:
    """Return a list of build definition files under *path*.

    The helper prefers the ``fd`` command if available, then falls back to
    ``find`` and finally to walking the directory tree with ``os.walk``. Paths
    are returned relative to *path*.
    """
    found: List[str] = []
    patterns = list(patterns or BUILD_PATTERNS)

    if shutil.which("fd"):
        for pattern in patterns:
            try:
                result = subprocess.run(
                    ["fd", "-HI", "-t", "f", pattern, path],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                warnings.warn(f"fd failed for pattern {pattern}: {e}")
                continue
            found.extend(result.stdout.splitlines())
    elif shutil.which("find"):
        for pattern in patterns:
            try:
                result = subprocess.run(
                    ["find", path, "-name", pattern, "-type", "f"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                warnings.warn(f"find failed for pattern {pattern}: {e}")
                continue
            found.extend(result.stdout.splitlines())
    else:
        for pattern in patterns:
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
