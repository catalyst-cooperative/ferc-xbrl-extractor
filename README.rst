===============================================================================
ferc-xbrl-extract
===============================================================================

.. readme-intro

The Federal Energy Regulatory Commission (FERC) has moved to collecting and distributing
data using `XBRL <https://en.wikipedia.org/wiki/XBRL>`__. XBRL is primarily designed for
financial reporting, and has been adopted by regulators in the US and other countries.
Much of the tooling in the XBRL ecosystem is targeted towards filers, and rendering
individual filings in a human readable way, but there is very little targeted towards
accessing and analyzing large collections of filings. This tool is designed to provide
that functionality for FERC XBRL data. Specifically, it can extract data from a set of
XBRL filings, and write that data to a SQLite database whose structure is generated from
an XBRL Taxonomy. While each XBRL instance contains a reference to a taxonomy,
this tool requires a path to a single taxonomy that will be used to interpret all
instances being processed. This means even if instances were created from different
versions of a Taxonomy, the provided taxonomy will be used when processing all of these
instances, so the output database will have a consistent structure. For more information
on the technical details of the XBRL extraction, see the docs.

As of this point in time this tool is only tested with FERC Form 1, but is intended
to extend support to other FERC forms. It is possible it could be used with non-FER
taxonomies with some tweaking, but we do not provide any official support for
non-FERC data.

Usage
-----

Installation
^^^^^^^^^^^^

To install using conda, run the following command, and activate the environment.

.. code-block:: console

    $ conda env create -f environment.yml

Activate:

.. code-block:: console

    $ conda activate ferc-xbrl-extractor


CLI
^^^

This tool can be used as a library, as it is in `PUDL <https://github.com/catalyst-cooperative/pudl>`__,
or there is a CLI provided for interacting with XBRL data. The only required options
for the CLI are a path to the filings to be extracted, and a path to the output
SQLite database. The path to the filings can point to a directory full of XBRL
Filings, a single XBRL filing, or a zipfile with XBRL filings. If
the path to the database points to an existing database, the ``--clobber`` option
can be used to drop all existing data before performing the extraction.

.. code-block:: console

    $ xbrl_extract {path_to_filings} {path_to_database}

This repo contains a small selection of FERC Form 1 filings from 2021 in the
``examples`` directory. To test the tool on these filings, use the command

.. code-block:: console

    $ xbrl_extract examples/ferc1-2021-sample.zip ./ferc1-2021-sample.sqlite

By default, the CLI will use the 2022 version of the FERC Form 1 Taxonomy to create
the structure of the output database, and it will obtain the taxonomy directly from
the FERC web server. To specify a different taxonomy use the ``--taxonomy`` option. This
can be either a URL pointing to a taxonomy entry point, or a path to a local zipfile.
The following command demonstrates this option using the same URL that would be used by
default.

.. code-block:: console

    $ xbrl_extract examples/ferc1-2021-sample.zip ./ferc1-2021-sample.sqlite \
        --taxonomy https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd

When using the ``--taxonomy`` option to read the taxonomy from a zipfile, the
``--archive-path`` option is also required. This option is used to indicate the path to
the taxonomy entry point within the zipfile. NOTE: This will likely change in the future
to automatically detect the entry point as this interface is clunky. To demonstrate, the
FERC Form 1 2021 taxonomy is included in the examples directory. This can be used with
the following command.

.. code-block:: console

    $ xbrl_extract examples/ferc1-2021-sample.zip ./ferc1-2021-sample.sqlite \
        --taxonomy examples/taxonomy.zip \
        --archive-path taxonomy/form1/2021-01-01/form/form1/form-1_2021-01-01.xsd

Parsing XBRL filings can be a time consuming and CPU heavy task, so this tool
implements some basic multiprocessing to speed this up. It uses a
`process pool <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor>`__
to do this. There are two options for configuring the process pool, ``--batch-size``
and ``--workers``. The batch size configures how many filings will be processed by
each child process at a time, and workers specifies how many child processes to
create in the pool. It may take some experimentation to get these options
optimally configured. The following command will use 5 worker processes to process
batches of 50 filings at a time.

.. code-block:: console

    $ xbrl_extract examples/ferc1-2021-sample.zip ./ferc1-2021-sample.sqlite \
        --workers 5 \
        --batch-size 50

There are also several options included for extracting metadata from the taxonomy.
First is the ``--save-datapackage`` command to save a
`frictionless datapackage <https://specs.frictionlessdata.io/data-package/>`__
descriptor as JSON, which annotates the generated SQLite database. There is also the
``--metadata-path`` option, which writes more extensive taxonomy metadata to a json
file, grouped by table name. See the :mod:`ferc_xbrl_extractor.arelle_interface` module
for more info on the extracted metadata. To create both of these files using the example
filings and taxonomy, run the following command.

.. code-block:: console

    $ xbrl_extract examples/ferc1-2021-sample.zip ./ferc1-2021-sample.sqlite \
        --taxonomy examples/taxonomy.zip \
        --archive-path taxonomy/form1/2021-01-01/form/form1/form-1_2021-01-01.xsd \
        --metadata-path metadata.json \
        --save-datapackage datapackage.json
