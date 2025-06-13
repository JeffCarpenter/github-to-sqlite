from setuptools import setup
import os

VERSION = "2.9"


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
    version=VERSION,
    packages=["github_to_sqlite"],
    entry_points="""
        [console_scripts]
        github-to-sqlite=github_to_sqlite.cli:cli
    """,
    install_requires=[
        "sqlite-utils>=2.7.2",
        "requests",
        "PyYAML",
        "sentence-transformers",
        "sqlite-vec",
        "nltk",
        "onnx",
        "pydantic>=2.0",
        "tokenizers",
    ],
    extras_require={
        "test": ["pytest", "pytest-cov", "requests-mock", "bs4", "mypy", "ruff"],
        "semantic_chunkers": [
            "semantic-chunkers @ https://github.com/aurelio-labs/semantic-chunkers/archive/refs/tags/v0.1.1.tar.gz"
        ],
        "vector-search-index": ["sentence-transformers[onnx]", "sqlite-vec"],
        "gpu": ["sentence-transformers[onnx-gpu]"],
        "docs": ["sphinx", "sphinx-rtd-theme"],
    },
    tests_require=["github-to-sqlite[test]"],
)
