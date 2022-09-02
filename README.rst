===============================================================================
ferc-xbrl-extract
===============================================================================

.. readme-intro

The Federal Energy Regulatory Commission (FERC) has moved to collecting and distributing data using `XBRL <https://en.wikipedia.org/wiki/XBRL>`__. XBRL is primarily designed for financial reporting, and has been adopted by regulators in the US and other countries. Much of the tooling in the XBRL ecosystem is targeted towards filers, and rendering individual filings in a human readable way, but there is very little targeted towards accessing and analyzing large collections of filings. This tool is designed to provide that functionality for FERC XBRL data. Specifically, it can extract data from a set of XBRL filings, and write that data to a SQLite database whose structure is generated from an XBRL `Taxonomy <https://en.wikipedia.org/wiki/XBRL#XBRL_Taxonomy>`__. While each XBRL instance contains a reference to a taxonomy, this tool requires a path to a single taxonomy that will be used to interpret all instances being processed. This means even if instances were created from different versions of a Taxonomy, the provided taxonomy will be used when processing all of these instances, so the output database will have a consistent structure. For more information on the technical details of the XBRL extraction, see the docs.

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

    $ conda activate ferc-xbrl-extract


CLI
^^^

This tool can be used as a library, as it is in `PUDL <https://github.com/catalyst-cooperative/pudl>`__,
or there is a CLI provided for interacting with XBRL data. The only required options
for the CLI are a path a single XBRL filing, or directory of XBRL filings, and a
path to the SQLite database.

.. code-block:: console

    $ xbrl_extract {path_to_filings} {path_to_database}

By default, the CLI will use the 2022 version of the FERC Form 1 Taxonomy to create
the structure of the output database. To specify a different taxonomy use the
``--taxonomy`` option.

.. code-block:: console

    $ xbrl_extract {path_to_filings} {path_to_database} --taxonomy {url_of_taxonomy}

Parsing XBRL filings can be a time consuming and CPU heavy task, so this tool
implements some basic multiprocessing to speed this up. It uses a
`process pool <https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ProcessPoolExecutor>`__
to do this. There are two options for configuring the process pool, ``--batch-size``
and ``--workers``. The batch size configures how many filings will be processed by
each child process at a time, and workers specifies how many child processes to
create in the pool. It may take some experimentation to get these options
optimally configured.

.. code-block:: console

    $ xbrl_extract {path_to_filings} {path_to_database} --workers {number_of_processes} --batch-size {filings_per_batch}
