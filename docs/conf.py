import os
import sys

sys.path.insert(0, os.path.abspath('..'))

project = 'github-to-sqlite'
author = 'Simon Willison'
release = '2.9'

extensions = ['sphinx.ext.autodoc']

html_theme = 'sphinx_rtd_theme'
