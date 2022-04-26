===============================================================================
xbrl-extract
===============================================================================

.. readme-intro

Utility for extracting data from `XBRL <https://en.wikipedia.org/wiki/XBRL>`__ filings into a SQLite database. The utility requires a path to one or more XBRL filings, and a path to a SQLite database. If the database does not exist, it will be created. For each XBRL instance, the taxonomy is dynamically retrieved and parsed using the XBRL library/tool, `Arelle <https://arelle.org/arelle/>`__. A SQL table will be generated for each Fact Table defined in the taxonomy. The XBRL context becomes the primary key for every table. This is a composite key containing the entity identifier, time period, and any other dimensions defined for the table in question. The instances are parsed in parallel using a thread pool to attempt to improve performance when parsing a large number of filings. The number of worker threads can specified explicitly using the ``--threads`` option.

Installation
===============================================================================
To install using conda, run the following command, and activate the environment.

``conda env create -f environment.yml``


CLI
===============================================================================
The only required options for the CLI are the path to the filings and the path to
the output database, specified as follows:

``xbrl_extract {path_to_filings} {path_to_database}``
