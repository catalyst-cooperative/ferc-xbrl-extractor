"""Configuration file for the Sphinx documentation builder."""
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import datetime
import importlib.metadata
import os
import shutil
from pathlib import Path

DOCS_DIR = Path(__file__).parent.resolve()

# -- Path setup --------------------------------------------------------------
# We are building and installing the pudl package in order to get access to
# the distribution metadata, including an automatically generated version
# number via pkg_resources.get_distribution() so we need more than just an
# importable path.

# The full version, including alpha/beta/rc tags
release = importlib.metadata.version("catalystcoop.ferc_xbrl_extractor")

# -- Project information -----------------------------------------------------

project = "FERC XBRL Extractor"
copyright = (  # noqa: A001
    f"2022-{datetime.date.today().year}, Catalyst Cooperative, CC-BY-4.0"
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
    "sphinx_llm.txt",
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
issues_github_path = "catalyst-cooperative/ferc-xbrl-extractor"

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
# If PUDL_DOCS_DISABLE_INTERSPHINX is set, disable intersphinx lookups. This can speed
# up the build and avoids issues with external sites being down.
if "PUDL_DOCS_DISABLE_INTERSPHINX" in os.environ:
    print("Disabling intersphinx lookups (PUDL_DOCS_DISABLE_INTERSPHINX is set).")
    intersphinx_mapping = {}


# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build"]

# -- Options for HTML output -------------------------------------------------

numfig = True

# The theme to use for HTML and HTML Help pages.
master_doc = "index"
html_theme = "pydata_sphinx_theme"
html_logo = "_static/catalyst_logo-200x200.png"
html_icon = "_static/favicon.ico"

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation. This repo's docs are small enough that the lefthand navigation
# sidebar isn't useful, so it's hidden site-wide via html_sidebars below.
html_theme_options = {
    "navigation_with_keys": True,
    "header_links_before_dropdown": 5,
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/catalyst-cooperative/ferc-xbrl-extractor",
            "icon": "fa-brands fa-github",
            "type": "fontawesome",
        },
        {
            "name": "Mastodon",
            "url": "https://mastodon.energy/@catalystcoop",
            "icon": "fa-brands fa-mastodon",
            "type": "fontawesome",
        },
        {
            "name": "Bluesky",
            "url": "https://bsky.app/profile/catalyst.coop",
            "icon": "fa-brands fa-bluesky",
            "type": "fontawesome",
        },
        {
            "name": "LinkedIn",
            "url": "https://www.linkedin.com/company/catalyst-cooperative/",
            "icon": "fa-brands fa-linkedin",
            "type": "fontawesome",
        },
        {
            "name": "Support PUDL",
            "url": "https://opencollective.com/pudl",
            "icon": "fa-solid fa-donate",
            "type": "fontawesome",
        },
    ],
    "secondary_sidebar_items": {
        "**": ["page-toc", "sourcelink"],
    },
    # Preserve pydata-sphinx-theme's default footer_end ("theme-version") and
    # add a link to the sphinx_llm.txt generated llms.txt index, so agents
    # exploring the rendered site (rather than landing on a specific page)
    # can discover the markdown-friendly docs.
    "footer_end": [
        "theme-version",
        *(["llms-txt-link"] if "sphinx_llm.txt" in extensions else []),
    ],
}
# No lefthand navigation sidebar -- the docs here are small enough that it isn't
# useful, unlike PUDL's much larger documentation tree.
html_sidebars = {"**": []}


# -- Custom build operations -------------------------------------------------
def cleanup_rsts(app, exception):
    """Remove generated RST files when the build is finished."""
    (DOCS_DIR / "path/to/temporary/rst/file.rst").unlink()


def cleanup_csv_dir(app, exception):
    """Remove generated CSV files when the build is finished."""
    csv_dir = DOCS_DIR / "path/to/temporary/csv/dir/"
    if csv_dir.exists() and csv_dir.is_dir():
        shutil.rmtree(csv_dir)


def add_markdown_alternate_link(app, pagename, templatename, context, doctree):
    """Advertise the sphinx_llm.txt markdown twin of each page via <link rel="alternate">.

    sphinx_llm.txt generates a ``<page>.html.md`` file alongside every HTML
    page (see llms_txt_suffix_mode="auto" default), but doesn't add any
    in-page signal pointing to it. This makes that markdown version
    discoverable to crawlers/agents that check for standard alternate-format
    links, without requiring them to already know the llms.txt convention.
    """
    if pagename not in app.env.found_docs:
        # Skip generated non-document pages (search, genindex, 404, etc.)
        # that don't have a markdown counterpart.
        return
    # sphinx_llm.txt writes the markdown twin next to its HTML page (e.g.
    # dev/pudl_id_mapping.html -> dev/pudl_id_mapping.html.md), so a
    # same-directory-relative filename is all that's needed. We avoid
    # context["pathto"](pagename) here because it collapses same-page
    # self-references down to a bare "#", which would produce a broken
    # "#.md" href.
    markdown_filename = f"{pagename.rsplit('/', 1)[-1]}.html.md"
    link_tag = (
        '\n<link rel="alternate" type="text/markdown" '
        'title="Markdown version of this page" '
        f'href="{markdown_filename}" />'
    )
    context["metatags"] = context.get("metatags", "") + link_tag


def setup(app):
    """Add custom CSS defined in _static/custom.css."""
    app.add_css_file("custom.css")
    # Examples of custom docs build steps:
    # app.connect("build-finished", cleanup_rsts)
    # app.connect("build-finished", cleanup_csv_dir)
    # Only advertise markdown alternates if sphinx_llm.txt is actually
    # installed, loaded, and not explicitly disabled via llms_txt_enabled.
    if "sphinx_llm.txt" in app.extensions and getattr(
        app.config, "llms_txt_enabled", True
    ):
        app.connect("html-page-context", add_markdown_alternate_link)
