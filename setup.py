#!/usr/bin/env python
"""Extract xbrl filings to dataframes."""

from setuptools import find_packages, setup

setup(
    name="xbrl_extract",
    version="0.0.1",
    packages=find_packages("src"),
    package_dir={"": "src"},
    author="Catalyst Cooperative",
    description="Tool for extracting data from xbrl filings to dataframes",
    python_requires=">=3.8,<3.11",
    entry_points={
        "console_scripts": [
            "xbrl_extract = xbrl_extract.cli:main",
        ]
    },
    license="MIT",
    install_requires=[
        "pydantic>=1.9,<2",
        "coloredlogs~=15.0",
        "arelle @ git+https://github.com/Arelle/Arelle.git@master",
        "sqlalchemy>=1.4,<2",
        "pandas>=1.4,<1.5"
    ]
)
