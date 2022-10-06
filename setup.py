#!/usr/bin/env python
"""Extract xbrl filings to dataframes."""

from pathlib import Path

from setuptools import find_packages, setup

readme_path = Path(__file__).parent / "README.rst"
long_description = readme_path.read_text()

setup(
    name="catalystcoop.ferc_xbrl_extractor",
    description="A tool for extracting data from FERC XBRL Filings.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    # setuptools_scm lets us automagically get package version from GitHub tags
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
    author="Catalyst Cooperative",
    author_email="pudl@catalyst.coop",
    maintainer="Zach Schira",
    maintainer_email="zach.schira@catalyst.coop",
    url="",  # Can be repo or docs URL if no separate web page exists.
    project_urls={
        "Source": "https://github.com/catalyst-cooperative/ferc-xbrl-extract",
        "Documentation": "https://PACKAGE_NAME.readthedocs.io",
        "Issue Tracker": "https://github.com/catalyst-cooperative/ferc-xbrl-extract/issues",
    },
    keywords=["xbrl", "ferc", "financial"],
    python_requires=">=3.8,<3.11",
    license="MIT",
    install_requires=[
        "pydantic>=1.9,<2",
        "coloredlogs~=15.0",
        "catalystcoop.arelle-mirror==1.3.0",
        "frictionless>=4.4,<5",
        "sqlalchemy>=1.4,<2",
        "pandas>=1.4,<1.5",
        "stringcase~=1.2.0",
    ],
    extras_require={
        "dev": [
            "black>=22.0,<22.7",  # A deterministic code formatter
            "isort>=5.0,<5.11",  # Standardized import sorting
            "tox>=3.20,<3.26",  # Python test environment manager
            "twine>=3.3,<4.1",  # Used to make releases to PyPI
        ],
        "docs": [
            "doc8>=0.9,<1.1",  # Ensures clean documentation formatting
            "furo>=2022.4.7",
            "sphinx>=4,!=5.1.0,<5.1.2",  # The default Python documentation engine
            "sphinx-autoapi>=1.8,<1.10",  # Generates documentation from docstrings
            "sphinx-issues>=1.2,<3.1",  # Allows references to GitHub issues
        ],
        "tests": [
            "bandit>=1.6,<1.8",  # Checks code for security issues
            "coverage>=5.3,<6.5",  # Lets us track what code is being tested
            "doc8>=0.9,<1.1",  # Ensures clean documentation formatting
            "flake8>=4.0,<5.1",  # A framework for linting & static analysis
            "flake8-builtins>=1.5,<1.6",  # Avoid shadowing Python built-in names
            "flake8-colors>=0.1,<0.2",  # Produce colorful error / warning output
            "flake8-docstrings>=1.5,<1.7",  # Ensure docstrings are formatted well
            "flake8-rst-docstrings>=0.2,<0.3",  # Allow use of ReST in docstrings
            "flake8-use-fstring>=1.0,<1.5",  # Highlight use of old-style string formatting
            "mccabe>=0.6,<0.8",  # Checks that code isn't overly complicated
            "mypy>=0.942,<0.972",  # Static type checking
            "pep8-naming>=0.12,<0.14",  # Require PEP8 compliant variable names
            "pre-commit>=2.9,<2.21",  # Allow us to run pre-commit hooks in testing
            "pydocstyle>=5.1,<6.2",  # Style guidelines for Python documentation
            "pytest>=6.2,<7.2",  # Our testing framework
            "pytest-console-scripts>=1.1,<1.4",  # Allow automatic testing of scripts
            "pytest-cov>=2.10,<3.1",  # Pytest plugin for working with coverage
            "rstcheck[sphinx]>=5.0,<6.2",  # ReStructuredText linter
            "tox>=3.20,<3.26",  # Python test environment manager
        ],
        "types": [
            "types-setuptools",
        ],
    },
    # A controlled vocabulary of tags used by the Python Package Index.
    # Make sure the license and python versions are consistent with other arguments.
    # The full list of recognized classifiers is here: https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    # Directory to search recursively for __init__.py files defining Python packages
    packages=find_packages("src"),
    # Location of the "root" package:
    package_dir={"": "src"},
    # package_data is data that is deployed within the python package on the
    # user's system. setuptools will get whatever is listed in MANIFEST.in
    include_package_data=True,
    # entry_points defines interfaces to command line scripts we distribute.
    # Can also be used for other resource deployments, like intake catalogs.
    entry_points={
        "console_scripts": [
            "xbrl_extract = ferc_xbrl_extractor.cli:main",
        ]
    },
)
