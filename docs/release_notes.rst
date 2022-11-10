=======================================================================================
PACKAGE_NAME Release Notes
=======================================================================================

.. _release-v0-4-0:

---------------------------------------------------------------------------------------
0.4.0 (2022-10-6)
---------------------------------------------------------------------------------------

Parse archived taxonomies
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* Add support for parsing taxonomies from a local zipfile

.. _release-v0-3-0:

---------------------------------------------------------------------------------------
0.3.0 (2022-08-27)
---------------------------------------------------------------------------------------

Enable publication of raw SQLite databases to Datasette
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* Add support for specifying a subset of tables for extraction
* Add options for specifying output path for datapackage descriptors
* Fix docs generation, as well as various other CI improvements

.. _release-v0-2-0:

---------------------------------------------------------------------------------------
0.2.0 (2022-07-28)
---------------------------------------------------------------------------------------

Support All Forms
^^^^^^^^^^^^^^^^^
* Tested with FERC forms 1, 2, 6, 60, 714
* Adds options for selecting taxonomies from CLI

.. _release-v0-1-0:

---------------------------------------------------------------------------------------
0.1.0 (2022-06-28)
---------------------------------------------------------------------------------------

Initial Release
^^^^^^^^^^^^^^^^
* The FERC XBRL extractor supports extracting data from XBRL filings to
  produce a SQLite database
* It provides a CLI that takes a link to a taxonomy and a set of filings
  and can produce a database containing the extracted data.
* FERC form 1 is the only form that is officially tested and supported
