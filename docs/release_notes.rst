=======================================================================================
PACKAGE_NAME Release Notes
=======================================================================================

.. _release-v1-2-0:

---------------------------------------------------------------------------------------
1.2.0 (2023-10-06)
---------------------------------------------------------------------------------------

* Instead of combining multiple filings from one year, we track publication
  time of each filing and keep all filings. This allows downstream users to
  deduplicate facts from multiple filings.

.. _release-v1-1-0:

---------------------------------------------------------------------------------------
1.1.0 (2023-09-22)
---------------------------------------------------------------------------------------

* Fix high memory usage in v1.0.

.. _release-v1-0-1:

---------------------------------------------------------------------------------------
1.0.1 (2023-09-13)
---------------------------------------------------------------------------------------

* Minor patch for Pydantic 2.0 compatibility.

.. _release-v1-0-0:

---------------------------------------------------------------------------------------
1.0.0 (2023-09-07)
---------------------------------------------------------------------------------------

* Match facts that are missing some dimensions to their corresponding fact tables - see
  `this issue <https://github.com/catalyst-cooperative/pudl/issues/2755>`_.
* Multiple filings from one entity in a year are now combined as if later ones are
  updates to earlier ones instead of duplicated.
* Separate taxonomy archives from data archives, since data refers to taxonomies from a
  specific year.
* Update to Pandas 2.0 and loosen dependency pins on ``arelle`` (now ">=2.3,<3")

.. _release-v0-7-0:

---------------------------------------------------------------------------------------
0.7.0 (2022-12-9)
---------------------------------------------------------------------------------------

Group taxonomy metadata by table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* Change taxonomy metadata extraction to group by table name

.. _release-v0-6-0:

---------------------------------------------------------------------------------------
0.6.0 (2022-12-8)
---------------------------------------------------------------------------------------

Use official Arelle package
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* Change Arelle dependency to point to official PyPI package
* Explicitly reset locale to avoid error caused by Arelle

.. _release-v0-5-0:

---------------------------------------------------------------------------------------
0.5.0 (2022-11-23)
---------------------------------------------------------------------------------------

Fix bug causing some records to be excluded
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
* Use sorted tuple keys when looking up facts during parsing

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
