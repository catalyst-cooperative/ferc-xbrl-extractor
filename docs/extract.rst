===============================================================================
Parsing
===============================================================================

Taxonomy Parsing
^^^^^^^^^^^^^^^^
`Arelle <https://arelle.org/arelle/>`__ is a popular open source library for working with XBRL
data, and it is used for parsing the taxonomy. After parsing the taxonomy, each link
role or fact table is used to generate a table schema for a SQL table. This is done
by traversing down the concept DAG to find leaf nodes, and create a column for each
leaf node. After this process is complete, we can parse individual filings, and
populate these constructed tables with the data in the filing.

Filing Parsing
^^^^^^^^^^^^^^
While Arelle is helpful for parsing taxonomies, it has proven too slow for parsing
large sets of filings. So, we've used the `lxml <https://lxml.de/>`__ library to
directly parse filings ourselves. This is not too difficult as this individual XBRL
instances are a fairly simple XML structure that are easy to parse. These files
contain a list of contexts, and a list of facts that we read into custom data
structures. Next, we take the tables constructed during the taxonomy parsing, and
we find all reported facts that are contained in each table, and we populate a
dataframe using that information.
