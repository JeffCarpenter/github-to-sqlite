import subprocess
import shutil
import os


from github_to_sqlite.utils import find_build_files, BUILD_PATTERNS


def test_find_build_files_fd(monkeypatch):
    calls = []

    def fake_which(cmd):
        return '/usr/bin/fd' if cmd == 'fd' else None

    def fake_run(args, capture_output, text, check):
        pattern = args[4] if len(args) > 4 else args[1]
        calls.append((args[0], pattern))
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
        class R:
            def __init__(self):
                self.stdout = 'repo/' + pattern + '\n'
        return R()

    monkeypatch.setattr(shutil, 'which', fake_which)
    monkeypatch.setattr(subprocess, 'run', fake_run)

    result = find_build_files('repo')
    assert result == BUILD_PATTERNS
    assert calls


def test_walk_fallback(monkeypatch):
    def fake_which(cmd):
        return None

    def fake_walk(path):
        return [
            ('repo', ['sub'], ['pyproject.toml']),
            ('repo/sub', [], ['Cargo.toml', 'something.txt']),
        ]

    monkeypatch.setattr(shutil, 'which', fake_which)
    monkeypatch.setattr(os, 'walk', fake_walk)

    result = find_build_files('repo')
    assert set(result) == {'pyproject.toml', 'sub/Cargo.toml'}
