=======================================================================================
Release Notes
=======================================================================================

.. _release-v1-8-0:

---------------------------------------------------------------------------------------
1.8.0 (2025-12-28)
---------------------------------------------------------------------------------------

Modernize build and packaging
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* **Migrated from tox to Hatch** for environment and task management, providing faster
  dependency resolution and a more modern Python packaging experience.
* **Adopted uv** as the package installer.
* **Modernized build system** from setuptools to hatchling with hatch-vcs for version
  management from git tags.
* **Reorganized CI workflows** into parallel jobs for testing, linting, and
  documentation building, improving CI speed and clarity.
* Added support for **Python 3.14**.
* **Consolidated development documentation** from separate CONTRIBUTING.md into
  README.rst
* Updated README with instructions for using Hatch and uv.
* Updated ReadTheDocs configuration to use uv and Hatch.
* **Loosened dependency version constraints** Removed upper bounds where
  appropriate to reduce dependency conflicts for downstream users.
* **Added build attestations** for supply chain security using GitHub's attestation
  action.
* **Adopted OIDC trusted publishing** to PyPI, eliminating the need for API tokens.
* Removed twine dependency (Hatch validates packages during build).
* Split pytest workflow into separate test, lint, and docs-build jobs for better
  parallelization.

See PR :pr:`405`.

.. _release-v1-7-3:

---------------------------------------------------------------------------------------
1.7.3 (2025-12-03)
---------------------------------------------------------------------------------------

* **Revert to treating dates as strings**, deferring cleaning until downstream
  processing. :pr:`396`

.. _release-v1-7-2:

---------------------------------------------------------------------------------------
1.7.2 (2025-11-26)
---------------------------------------------------------------------------------------

* **Fix datetime type for publication date** to ensure proper handling across database
  backends. :pr:`392`

.. _release-v1-7-1:

---------------------------------------------------------------------------------------
1.7.1 (2025-11-19)
---------------------------------------------------------------------------------------

* Improve dtype handling for DuckDB and SQLite outputs. :pr:`388`
* Add integration test to verify DuckDB and SQLite tables are identical.

.. _release-v1-7-0:

---------------------------------------------------------------------------------------
1.7.0 (2025-11-16)
---------------------------------------------------------------------------------------

Support Output to DuckDB
^^^^^^^^^^^^^^^^^^^^^^^^

* **Add DuckDB output support** alongside existing SQLite output. :pr:`368`
* **Pin arelle version** to avoid pillow v12.0 compatibility issues. :pr:`382`

.. _release-v1-6-0:

---------------------------------------------------------------------------------------
1.6.0 (2025-04-28)
---------------------------------------------------------------------------------------

* **Make table name pattern more robust** to handle edge cases in XBRL taxonomy parsing.
  :pr:`320`

.. _release-v1-5-2:

---------------------------------------------------------------------------------------
1.5.2 (2025-04-12)
---------------------------------------------------------------------------------------

* **Add Python 3.13 support**. :pr:`318`

.. _release-v1-5-1:

---------------------------------------------------------------------------------------
1.5.1 (2024-07-17)
---------------------------------------------------------------------------------------

Multi-Taxonomy Support
^^^^^^^^^^^^^^^^^^^^^^

* **Fix datapackage generation from multiple taxonomies**. :pr:`242`
* Improve datapackage formatting.
* Fix examples in README with updated sample filings.
* Improve docstrings and comments throughout the codebase.

.. _release-v1-5-0:

---------------------------------------------------------------------------------------
1.5.0 (2024-07-02)
---------------------------------------------------------------------------------------

* Minor dependency updates and maintenance release.

.. _release-v1-4-0:

---------------------------------------------------------------------------------------
1.4.0 (2024-04-14)
---------------------------------------------------------------------------------------

* **Update to Frictionless v5** and ensure all tests pass with the new version.
  :pr:`213`

.. _release-v1-3-3:

---------------------------------------------------------------------------------------
1.3.3 (2024-03-26)
---------------------------------------------------------------------------------------

* **Add retry logic for taxonomy reading** to improve reliability with network issues.
  :pr:`205`

.. _release-v1-3-2:

---------------------------------------------------------------------------------------
1.3.2 (2024-01-20)
---------------------------------------------------------------------------------------

* **Add support for pandas 2.2**.
* Cache dimension snakecase operations for better performance.

.. _release-v1-3-1:

---------------------------------------------------------------------------------------
1.3.1 (2023-11-29)
---------------------------------------------------------------------------------------

* Fix warning suppression by using 'ignore' instead of 'once'.

.. _release-v1-3-0:

---------------------------------------------------------------------------------------
1.3.0 (2023-11-28)
---------------------------------------------------------------------------------------

* **Update to Pydantic v2** and migrate from Black to Ruff formatting. :pr:`169`
* Add Zenodo DOI badge to README.

.. _release-v1-2-1:

---------------------------------------------------------------------------------------
1.2.1 (2023-10-18)
---------------------------------------------------------------------------------------

* Add Python 3.12 support.

.. _release-v1-2-0:

---------------------------------------------------------------------------------------
1.2.0 (2023-10-12)
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
