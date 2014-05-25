import sys
from os import path

tree = path.dirname(path.dirname(path.abspath(__file__)))
sys.path.insert(0, tree)

import usercouch


# Project info
project = 'UserCouch'
copyright = '2014, Novacut Inc'
version = usercouch.__version__
release = usercouch.__version__


# General config
needs_sphinx = '1.2'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
]
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
exclude_patterns = ['_build']
pygments_style = 'sphinx'


# HTML config
html_theme = 'default'
html_static_path = ['_static']
htmlhelp_basename = 'UserCouchdoc'

