"""Configuration file for the Sphinx documentation builder."""
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import datetime
import shutil
from pathlib import Path

import pkg_resources

DOCS_DIR = Path(__file__).parent.resolve()

# -- Path setup --------------------------------------------------------------
# We are building and installing the pudl package in order to get access to
# the distribution metadata, including an automatically generated version
# number via pkg_resources.get_distribution() so we need more than just an
# importable path.

# The full version, including alpha/beta/rc tags
release = pkg_resources.get_distribution("catalystcoop.ferc_xbrl_extractor").version

# -- Project information -----------------------------------------------------

project = "New Catalyst Python Project"
copyright = (  # noqa: A001
    f"202X-{datetime.date.today().year}, Catalyst Cooperative, CC-BY-4.0"
)
author = "Catalyst Cooperative"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "autoapi.extension",
    "sphinx_issues",
    "sphinx_rtd_dark_mode",
]
todo_include_todos = True

# Automatically generate API documentation during the doc build:
autoapi_type = "python"
autoapi_dirs = [
    "../src/ferc_xbrl_extractor",
]
autoapi_ignore = [
    "*_test.py",
    "*/package_data/*",
]

# GitHub repo
issues_github_path = "catalyst-cooperative/repo_name"

# In order to be able to link directly to documentation for other projects,
# we need to define these package to URL mappings:
intersphinx_mapping = {
    "numpy": ("https://numpy.org/doc/stable/", None),
    "pandas": ("https://pandas.pydata.org/pandas-docs/stable", None),
    "pytest": ("https://docs.pytest.org/en/latest/", None),
    "python": ("https://docs.python.org/3", None),
    "scipy": ("https://docs.scipy.org/doc/scipy/", None),
    "setuptools": ("https://setuptools.pypa.io/en/latest/", None),
    "tox": ("https://tox.wiki/en/latest/", None),
}

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.

# user starts in dark mode
default_dark_mode = False

master_doc = "index"
html_theme = "sphinx_rtd_theme"
html_logo = "_static/catalyst_logo-200x200.png"
html_icon = "_static/favicon.ico"

html_context = {
    "display_github": True,  # Integrate GitHub
    "github_user": "catalyst-cooperative",  # Username
    "github_repo": "repo_name",  # Repo name
    "github_version": "main",  # Version
    "conf_py_path": "/docs/",  # Path in the checkout to the docs root
}

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    "collapse_navigation": True,
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]


# -- Custom build operations -------------------------------------------------
def cleanup_rsts(app, exception):
    """Remove generated RST files when the build is finished."""
    (DOCS_DIR / "path/to/temporary/rst/file.rst").unlink()


def cleanup_csv_dir(app, exception):
    """Remove generated CSV files when the build is finished."""
    csv_dir = DOCS_DIR / "path/to/temporary/csv/dir/"
    if csv_dir.exists() and csv_dir.is_dir():
        shutil.rmtree(csv_dir)


def setup(app):
    """Add custom CSS defined in _static/custom.css."""
    app.add_css_file("custom.css")
    # Examples of custom docs build steps:
    # app.connect("build-finished", cleanup_rsts)
    # app.connect("build-finished", cleanup_csv_dir)
