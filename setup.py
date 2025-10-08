from setuptools import setup
import os
import re


def get_version():
    """Extract version from __init__.py"""
    init_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "github_to_sqlite",
        "__init__.py"
    )
    with open(init_path, encoding="utf8") as f:
        content = f.read()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
        raise RuntimeError("Unable to find version string")


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="github-to-sqlite",
    description="Save data from GitHub to a SQLite database",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Simon Willison",
    url="https://github.com/dogsheep/github-to-sqlite",
    license="Apache License, Version 2.0",
    version=get_version(),
    packages=["github_to_sqlite"],
    entry_points="""
        [console_scripts]
        github-to-sqlite=github_to_sqlite.cli:app
    """,
    install_requires=["sqlite-utils>=2.7.2", "requests", "PyYAML", "typer"],
    extras_require={"test": ["pytest", "requests-mock", "bs4"]},
    tests_require=["github-to-sqlite[test]"],
)
