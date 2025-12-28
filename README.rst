===============================================================================
FERC XBRL Extractor
===============================================================================

.. readme-intro

.. image:: https://www.repostatus.org/badges/latest/active.svg
   :target: https://www.repostatus.org/#active
   :alt: Project Status: Active

.. image:: https://github.com/catalyst-cooperative/ferc-xbrl-extractor/actions/workflows/pytest.yml/badge.svg
   :target: https://github.com/catalyst-cooperative/ferc-xbrl-extractor/actions/workflows/pytest.yml
   :alt: pytest status

.. image:: https://img.shields.io/codecov/c/github/catalyst-cooperative/ferc-xbrl-extractor?style=flat&logo=codecov
   :target: https://codecov.io/gh/catalyst-cooperative/ferc-xbrl-extractor
   :alt: Codecov Test Coverage

.. image:: https://img.shields.io/readthedocs/catalystcoop-ferc-xbrl-extractor?style=flat&logo=readthedocs
   :target: https://catalystcoop-ferc-xbrl-extractor.readthedocs.io/en/latest/
   :alt: Read the Docs Build Status

.. image:: https://img.shields.io/pypi/v/catalystcoop.ferc-xbrl-extractor
   :target: https://pypi.org/project/catalystcoop.ferc-xbrl-extractor/
   :alt: PyPI Latest Version

.. image:: https://img.shields.io/conda/vn/conda-forge/catalystcoop.ferc_xbrl_extractor
   :target: https://anaconda.org/conda-forge/catalystcoop.ferc_xbrl_extractor
   :alt: conda-forge Version

.. image:: https://img.shields.io/pypi/pyversions/catalystcoop.ferc-xbrl-extractor
   :target: https://pypi.org/project/catalystcoop.ferc-xbrl-extractor/
   :alt: Supported Python Versions

.. :image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
   :target: https://github.com/astral-sh/ruff
   :alt: Formatted by ruff

.. image:: https://results.pre-commit.ci/badge/github/catalyst-cooperative/ferc-xbrl-extractor/main.svg
   :target: https://results.pre-commit.ci/latest/github/catalyst-cooperative/ferc-xbrl-extractor/main
   :alt: pre-commit CI

.. image:: https://zenodo.org/badge/471019769.svg
  :target: https://zenodo.org/doi/10.5281/zenodo.10020145
   :alt: Zenodo DOI

The Federal Energy Regulatory Commission (FERC) has moved to collecting and distributing
data using `XBRL <https://en.wikipedia.org/wiki/XBRL>`__. XBRL is primarily designed for
financial reporting, and has been adopted by regulators in the US and other countries.
Much of the tooling in the XBRL ecosystem is targeted towards filers, and rendering
individual filings in a human readable way, but there is very little targeted towards
accessing and analyzing large collections of filings.

The FERC XBRL Extractor is designed to provide that functionality for FERC XBRL data.
The library can extract data from a set of XBRL filings, and write that data to `SQLite
<https://sqlite.org>`__ or `DuckDB <https://duckdb.org>`__ databases whose structure is
derived from an XBRL Taxonomy. While each XBRL instance contains a reference to a
taxonomy, this tool requires a path to a single taxonomy that will be used to interpret
all instances being processed. This means even if instances were created from different
versions of a taxonomy, the provided taxonomy will be used when processing all of these
instances, so the output database will have a consistent structure. For more information
on the technical details of the XBRL extraction, see the docs.

`Catalyst Cooperative <https://github.com/catalyst-cooperative>`__ is currently using
this tool to extract and publish the following FERC data. These outputs are updatded at
least annually, and typically quarterly.

.. list-table::
   :header-rows: 1

   * - FERC Form
     - Taxonomy
     - Raw Data
     - SQLite
     - DuckDB
   * - `Form 1 (Electricity) <https://www.ferc.gov/industries-data/electric/general-information/electric-industry-forms/form-1-electric-utility-annual>`__
     - `Browse <https://xbrlview.ferc.gov/yeti/resources/yeti-gwt/Yeti.jsp#tax~(id~8*v~150)!net~(a~143*l~35)!lang~(code~en)!rg~(rg~4*p~1)>`__
     - `10.5281/zenodo.4127043 <https://doi.org/10.5281/zenodo.4127043>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc1_xbrl.sqlite.zip>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc1_xbrl.duckdb>`__
   * - `Form 2 (Natural Gas) <https://www.ferc.gov/industries-data/natural-gas/industry-forms/form-2-2a-3-q-gas-historical-vfp-data>`__
     - `Browse <https://xbrlview.ferc.gov/yeti/resources/yeti-gwt/Yeti.jsp#tax~(id~1*v~149)!net~(a~3*l~4)!lang~(code~en)!rg~(rg~5*p~1)>`__
     - `10.5281/zenodo.5879542 <https://doi.org/10.5281/zenodo.5879542>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc2_xbrl.sqlite.zip>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc2_xbrl.duckdb>`__
   * - `Form 6 (Oil) <https://www.ferc.gov/industries-data/electric/general-information/electric-industry-forms/form-66-q-overview-orders>`__
     - `Browse <https://xbrlview.ferc.gov/yeti/resources/yeti-gwt/Yeti.jsp#tax~(id~4*v~148)!net~(a~63*l~19)!lang~(code~en)!rg~(rg~6*p~1)>`__
     - `10.5281/zenodo.7126395 <https://doi.org/10.5281/zenodo.7126395>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc6_xbrl.sqlite.zip>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc6_xbrl.duckdb>`__
   * - `Form 60 (Service Companies) <https://www.ferc.gov/ferc-online/ferc-online/filing-forms/service-companies-filing-forms/form-60-annual-report>`_
     - `Browse <https://xbrlview.ferc.gov/yeti/resources/yeti-gwt/Yeti.jsp#tax~(id~6*v~147)!net~(a~103*l~29)!lang~(code~en)!rg~(rg~7*p~1)>`__
     - `10.5281/zenodo.7126434 <https://doi.org/10.5281/zenodo.7126434>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc60_xbrl.sqlite.zip>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc60_xbrl.duckdb>`__
   * - `Form 714 (Balancing Authorities) <https://www.ferc.gov/industries-data/electric/general-information/electric-industry-forms/form-no-714-annual-electric>`__
     - `Browse <https://xbrlview.ferc.gov/yeti/resources/yeti-gwt/Yeti.jsp#tax~(id~7*v~146)!net~(a~123*l~34)!lang~(code~en)!rg~(rg~8*p~1)>`__
     - `10.5281/zenodo.4127100 <https://doi.org/10.5281/zenodo.4127100>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc714_xbrl.sqlite.zip>`__
     - `Download <https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/nightly/ferc714_xbrl.duckdb>`__

Usage
-----

Installation
^^^^^^^^^^^^

The package can be installed `from PyPI
<https://pypi.org/project/catalystcoop.ferc-xbrl-extractor/>`__ or `conda-forge
<https://anaconda.org/channels/conda-forge/packages/catalystcoop.ferc_xbrl_extractor/overview>`__
using your package manager of choice:

From PyPI
~~~~~~~~~

.. code-block:: bash

    pip install catalystcoop.ferc-xbrl-extractor
    uv pip install catalystcoop.ferc-xbrl-extractor

From ``conda-forge``
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    conda install catalystcoop.ferc_xbrl_extractor
    mamba install catalystcoop.ferc_xbrl_extractor
    pixi install catalystcoop.ferc_xbrl_extractor

Input Data
^^^^^^^^^^

The FERC XBRL Extractor is generally intended to consume raw XBRL filings and taxonomy
information from one of the archives Catalyst Cooperative has published on `Zenodo
<https://zenodo.org>`__. Each supported form has its own archive lineage, with new
snapshots captured from FERC's XBRL filing RSS feeds on a regular basis (see links in
the table above). The tool also expects to receive a zipfile containing archived
taxonomies.

The archived filings and taxonomies are both produced using the `pudl-archiver
<https://github.com/catalyst-cooperative/pudl-archiver>`__.  The extractor will parse
all taxonomies in the archive, then use the taxonomy referenced in each filing while
parsing it.

CLI
^^^

This tool can be used as a library, as it is in `PUDL
<https://github.com/catalyst-cooperative/pudl>`__. There is also a CLI provided for
interacting with XBRL data. The only required options for the CLI are a path to the
filings to be extracted, and a path to the output database. The path to the
filings can point to a directory full of XBRL Filings, a single XBRL filing, or a
zipfile with XBRL filings. If the specified output database already exists, it will be
overwritten.

.. code-block:: bash

    xbrl_extract {path_to_filings} --sqlite-path {path_to_database}

This repo contains a small selection of FERC Form 1 filings from 2021, along with
an archive of taxonomies in the ``examples`` directory. To test the tool on these
filings, use the command:

.. code-block:: bash

    xbrl_extract examples/ferc1-2021-sample.zip \
        --sqlite-path ./ferc1-2021-sample.sqlite \
        --taxonomy examples/ferc1-xbrl-taxonomies.zip

Parsing XBRL filings can be a time consuming and CPU heavy task, so this tool
implements some basic multiprocessing to speed this up. It uses a
`process pool <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor>`__
to do this. There are two options for configuring the process pool, ``--batch-size``
and ``--workers``. The batch size configures how many filings will be processed by
each child process at a time, and workers specifies how many child processes to
create in the pool. It may take some experimentation to get these options
optimally configured. The following command will use 5 worker processes to process
batches of 50 filings at a time. It will also output both SQLite and DuckDB.

.. code-block:: bash

    xbrl_extract examples/ferc1-2021-sample.zip \
        --sqlite-path ferc1-2021-sample.sqlite \
        --duckdb-path ferc1-2021-sample.duckdb \
        --taxonomy examples/ferc1-xbrl-taxonomies.zip \
        --workers 5 \
        --batch-size 50

There are also several options included for extracting metadata from the taxonomy.
First is the ``--datapackage-path`` command to save a
`frictionless datapackage <https://specs.frictionlessdata.io/data-package/>`__
descriptor as JSON, which annotates the generated SQLite database. There is also the
``--metadata-path`` option, which writes more extensive taxonomy metadata to a json
file, grouped by table name. See the ``ferc_xbrl_extractor.arelle_interface`` module
for more info on the extracted metadata. To create both of these files using the example
filings and taxonomy, run the following command.

.. code-block:: bash

    xbrl_extract examples/ferc1-2021-sample.zip \
        --sqlite-path /ferc1-2021-sample.sqlite \
        --taxonomy examples/ferc1-xbrl-taxonomies.zip \
        --metadata-path metadata.json \
        --datapackage-path datapackage.json

Contributing / Development
--------------------------

This project uses `uv <https://docs.astral.sh/uv/>`__ for dependency management and
`Hatch <https://hatch.pypa.io/>`__ for environment and task management. It also
includes several git pre-commit hooks that help enforce standard coding practices.
To set up the environment for development first ensure you have
`uv installed <https://docs.astral.sh/uv/getting-started/installation/>`__ and then:

.. code-block:: bash

    # Clone the repository to your local machine
    git clone https://github.com/catalyst-cooperative/ferc-xbrl-extractor.git
    cd ferc-xbrl-extractor
    # Create the development environment with hatch
    uv tool install hatch
    hatch env create
    # Install the pre-commit hooks
    hatch run pre-commit install

All available development environments and commands can be shown with:

.. code-block:: bash

   $ hatch env show

Some of the available commands:

.. code-block:: bash

    # Run all tests and collect coverage
    hatch run test:all
    # Run only unit tests
    hatch run test:unit
    # Run only integration tests
    hatch run test:integration
    # Run linters and formatters
    hatch run lint:all
    # Check code without modifying
    hatch run lint:check
    # Format code
    hatch run lint:format
    # Build documentation
    hatch run docs:build
    # Check documentation formatting
    hatch run docs:check

Code style is enforced using `ruff <https://docs.astral.sh/ruff/>`__ with configuration
in ``pyproject.toml``.

PUDL Sustainers
---------------

This package is part of the `Public Utility Data Liberation (PUDL) project
<https://github.com/catalyst-cooperative/pudl>`__.

The PUDL Sustainers provide ongoing financial support to ensure the open data keeps
flowing, and the project is sustainable long term. They're also involved in our
quarterly planning process. To learn more see `the PUDL Project on Open Collective
<https://opencollective.com/pudl>`__.
