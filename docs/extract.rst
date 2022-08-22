===============================================================================
Background
===============================================================================

Filing
^^^^^^

A single XBRL filing or instance contains a list of facts and a list of contexts.
A fact is considered to be an atomic unit of data. It contains a single value, a
name, data type, and a reference to a context. The context provides information relevant
to interpret the fact. A context always contains a time period and entity that the
pertains to, as well as any other "dimensions" that can be defined to further
identify the fact in question.

Taxonomy
^^^^^^^^

An XBRL taxonomy provides important metadata and structure for interpreting
facts reported in a filing. All facts that can be reported for a given taxonomy have
a Concept defined in the taxonomy. Concepts contain metadata that provide a description,
units, and other helpful information. Not all concepts are facts, however, they can also
represent a group of facts and provide information about that group.

To group facts into "fact tables", a taxonomy defines relationships between concepts.
These relationships are defined in a Link Role. Each link role contains a Directed
Acyclic Graph (DAG) of concepts. Concepts that correspond to individual facts will
be the "leaf nodes" in this graph.

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
