===============================================================================
XBRL Glossary
===============================================================================

.. glossary::

  Axis
    Axes are defined in the :term:`Taxonomy`, and are used as a part of the
    :term:`Context` to identify a :term:`Fact` beyond the default
    entity, and :term:`Period`. Axes can be either typed or explicit. An
    explicit Axis will have all of its allowable values defined in the taxonomy. A
    typed Axis will instead allow a filer to input their own values for the Axis.

  Concept
    Concepts are defined in the :term:`Taxonomy`, and describe what sort of
    :term:`Facts <Fact>` can be reported in a :term:`Filing`. They provide a written
    description, and other metadata that the taxonomy creator chooses to include.
    Not all Concepts will have Facts they are directly associated with. This is
    because Concepts can also be used as a part of a Concept tree to define
    relationships with other Concepts. The root of such a tree is a :term:`Link Role`.

  Context
    A context provides important information for identifying/interpreting a
    :term:`Fact`. Every context contains both an entity identifier, and a
    Period. A context can also contain user defined :term:`Axes <Axis>`.

  Fact
    An XBRL fact is considered to be an atomic unit of data. It contains a single value,
    with a name that corresponds to a :term:`Concept`, and a reference to a
    :term:`Context`.

  Filing
    An XBRL filing is how data is actually reported. It contains a list of
    Facts, and a list of :term:`Contexts <Context>`. A filing is associated with a
    :term:`Taxonomy` that is used to interpret :term:`Facts <Fact>` and their
    relationships to one another.

  Link Role
    Link Roles are defined in the :term:`Taxonomy`, and create relationships between
    :term:`Concepts <Concept>`. This is done by creating a Directed Acyclic Graph
    (DAG) of Concepts, with the Link Role as the root. The only Concepts that will
    have :term:`Facts <Fact>` associated with them are those at the bottom of the
    tree without any child Concepts.

  Taxonomy
    An XBRL taxonomy provides important metadata and structure for interpreting
    :term:`Facts <Fact>` reported in a filing. All facts that can be reported for a
    given taxonomy have a :term:`Concept` defined in the taxonomy. Taxonomies also
    contain :term:`Link Roles <Link Role>` that define relationships between facts
    that creates some structure for the data.

  Period
    A period defines the time frame that a :term:`Fact` pertains to. A period can be
    either a duration or instant, where a duration period is used for facts that
    pertain to a specific time interval, while an instant period is true at exactly
    one point in time.
