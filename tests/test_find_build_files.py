import subprocess
import shutil


from github_to_sqlite.utils import find_build_files, _post_process_build_files


def test_find_build_files_fd(monkeypatch):
    calls = []

    def fake_which(cmd):
        return '/usr/bin/fd' if cmd == 'fd' else None

    def fake_run(args, capture_output, text, check):
        pattern = args[4] if len(args) > 4 else args[1]
        calls.append((args[0], pattern))
        if pattern == 'package.json':
            raise subprocess.CalledProcessError(1, args)
        class Res:
            def __init__(self):
                self.stdout = {
                    'pyproject.toml': 'a/pyproject.toml\n',
                    'package.json': '',
                    'Cargo.toml': 'Cargo.toml\n',
                    'Gemfile': ''
                }[pattern]
        return Res()

    monkeypatch.setattr(shutil, 'which', fake_which)
    monkeypatch.setattr(subprocess, 'run', fake_run)

    result = find_build_files('repo')
    assert result == ['a/pyproject.toml', 'Cargo.toml']
    assert calls


def test_find_fallback(monkeypatch):
    calls = []

    def fake_which(cmd):
        if cmd == 'find':
            return '/usr/bin/find'
        return None

    def fake_run(args, capture_output, text, check):
        pattern = args[3]
        calls.append((args[0], pattern))
        if pattern == 'package.json':
            raise subprocess.CalledProcessError(1, args)
        class R:
            def __init__(self):
                self.stdout = 'repo/' + pattern + '\n'
        return R()

    monkeypatch.setattr(shutil, 'which', fake_which)
    monkeypatch.setattr(subprocess, 'run', fake_run)

    result = find_build_files('repo')
    assert 'package.json' not in result
    assert 'pyproject.toml' in result and 'Cargo.toml' in result
    assert calls


def test_walk_fallback(monkeypatch, tmp_path):
    def fake_which(cmd):
        return None

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "pyproject.toml").write_text("")
    sub = repo_dir / "sub"
    sub.mkdir()
    (sub / "Cargo.toml").write_text("")

    monkeypatch.setattr(shutil, "which", fake_which)

    result = find_build_files(str(repo_dir))
    assert set(result) == {"pyproject.toml", "sub/Cargo.toml"}


def test_find_build_files_custom_patterns(monkeypatch, tmp_path):
    repo_dir = tmp_path / "r"
    repo_dir.mkdir()
    (repo_dir / "BUILD.yaml").write_text("")

    monkeypatch.setattr(shutil, "which", lambda cmd: None)

    result = find_build_files(str(repo_dir), patterns=["BUILD.yaml"])
    assert result == ["BUILD.yaml"]


def test_post_process_build_files():
    base = "/home/user/repo"
    found = [
        "/home/user/repo/a/pyproject.toml",
        "/home/user/repo/.git/config",
        "/home/user/repo/node_modules/pkg.json",
        "/home/user/repo/a/pyproject.toml",
    ]
    result = _post_process_build_files(found, base)
    assert result == ["a/pyproject.toml"]

