import sys
from os import path

tree = path.dirname(path.dirname(path.abspath(__file__)))
sys.path.insert(0, tree)

import usercouch


project = 'UserCouch'
copyright = '2012, Novacut Inc'
version = usercouch.__version__[:5]
release = usercouch.__version__


needs_sphinx = '1.1'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.coverage',
]
templates_path = ['_templates']
source_suffix = '.rst'
master_doc = 'index'
exclude_patterns = ['_build']
pygments_style = 'sphinx'


html_theme = 'default'
html_static_path = ['_static']
htmlhelp_basename = 'UserCouchdoc'

