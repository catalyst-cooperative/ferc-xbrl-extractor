"""XBRL prototype structures."""
import io
import json
from pathlib import Path
from typing import Any, Literal

import pydantic
from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept, ModelType
from pydantic import AnyHttpUrl, BaseModel

from ferc_xbrl_extractor.arelle_interface import (
    Metadata,
    load_taxonomy,
    load_taxonomy_from_archive,
)

ConceptDict = dict[str, ModelConcept]


class XBRLType(BaseModel):
    """Pydantic model that defines the type of a Concept.

    XBRL provides an inheritance model for defining types. There are a number of
    standardized types, as well as support for user defined types. For simplicity,
    this model stores just the name of the type, and the base type which it is
    derived from. The base type is then used for determining what type to use in
    the resulting database. The list of base types defined/dealt with here is not
    a comprehensive list of all types in the XBRL standard, but it does contain all
    types used in the FERC Form 1 taxonomy.
    """

    name: str = "string"
    base: Literal[
        "string", "decimal", "gyear", "integer", "boolean", "date", "duration"
    ] = "string"

    @classmethod
    def from_arelle_type(cls, arelle_type: ModelType) -> "XBRLType":
        """Construct XBRLType class from arelle ModelType."""
        return cls(name=arelle_type.name, base=arelle_type.baseXsdType.lower())

    def get_pandas_type(self) -> str | None:
        """Return corresponding pandas type.

        Gets a string representation of the pandas type best suited to represent the
        base type.
        """
        if self.base == "string" or self.base == "date" or self.base == "duration":
            return "string"
        if self.base == "decimal":
            return "Float64"
        if self.base == "gyear" or self.base == "integer":
            return "Int64"
        if self.base == "boolean":
            return "boolean"
        return None

    def get_schema_type(self) -> str:
        """Return string specifying type for a frictionless table schema."""
        if self.base == "gyear":
            return "year"
        if self.base == "decimal":
            return "number"
        if self.base == "duration":
            return "string"
        return self.base


class Concept(BaseModel):
    """Pydantic model that defines an XBRL taxonomy Concept.

    A :term:`Concept` in the XBRL context can represent either a single fact or a
    'container' for multiple facts. If child_concepts is empty, that indicates
    that the Concept is a single fact.
    """

    name: str
    standard_label: str
    documentation: str
    type_: XBRLType = pydantic.Field(alias="type")
    period_type: Literal["duration", "instant"]
    child_concepts: "list[Concept]"
    metadata: Metadata | None = None

    @classmethod
    def from_list(cls, concept_list: list, concept_dict: ConceptDict) -> "Concept":
        """Construct a Concept from a list.

        The way Arelle represents the structure of the of a taxonomy is a
        bit unintuitive. Each concept is represented as a list with
        the first element being the string 'concept', the next two are
        dictionaries containing metadata (the first of these two dictionaries
        has a 'name' field that is used to look up concepts in the ConceptDict.
        The remaining elements in the list are child concepts of the current
        concept. These child concepts are represented using the same list structure.
        These nested lists Directed Acyclic Graph (DAG) of concepts that defines a
        fact table.

        Args:
            concept_list: List containing the Arelle representation of a concept.
            concept_dict: Dictionary mapping concept names to ModelConcept structures.
        """
        if concept_list[0] != "concept":
            raise ValueError("First element should be 'concept'")

        if not isinstance(concept_list[1], dict) or not isinstance(
            concept_list[2], dict
        ):
            raise TypeError("Second 2 elements should be dicts")

        concept = concept_dict[concept_list[1]["name"]]

        return cls(
            name=concept.name,
            standard_label=concept.label(XbrlConst.standardLabel),
            documentation=concept.label(XbrlConst.documentationLabel),
            type=XBRLType.from_arelle_type(concept.type),
            period_type=concept.periodType,
            child_concepts=[
                Concept.from_list(concept, concept_dict) for concept in concept_list[3:]
            ],
            metadata=Metadata.from_concept(concept),
        )

    def get_metadata(
        self, period_type: Literal["duration", "instant"]
    ) -> dict[str, dict[str, Any]]:
        """Get metadata from all leaf nodes in Concept tree.

        Leaf nodes in the Concept tree will become columns in output tables. This method
        will return the metadata only pertaining to these Concepts.

        Args:
            period_type: Return instant or duration concepts.

        Returns:
            A dictionary that maps Concept names to dictionaries of metadata.
        """
        metadata = {}
        # If Concept contains child Concepts, traverse down tree and add metadata from leaf nodes
        if len(self.child_concepts) > 0:
            for concept in self.child_concepts:
                metadata.update(concept.get_metadata(period_type))

        # If concept is leaf node return metadata
        else:
            if period_type == self.period_type:
                metadata[self.name] = self.metadata.dict()

        return metadata


Concept.update_forward_refs()


class LinkRole(BaseModel):
    """Pydantic model that defines an XBRL taxonomy linkrole.

    In XBRL taxonomies, Link Roles are used to group :term:`Concept` together in a
    meaningful way. These groups are often referred to as "Fact Tables". Link roles
    accomplish this by grouping Concepts into a Directed Acyclic Graph (DAG). In
    this graph, the leaf nodes in this graph represent individual facts, while other
    nodes represent containers of facts.
    """

    role: AnyHttpUrl
    definition: str
    concepts: Concept

    @classmethod
    def from_list(cls, linkrole_list: list, concept_dict: ConceptDict) -> "LinkRole":
        """Construct from list.

        Arelle represents link roles in a similar structure to concepts.
        It uses a list where the first element is the string 'linkRole', and the
        second is a dictionary of metadata. This dictionary contains a field
        'role' which is a URL pointing to where the link role is defined in the
        taxonomy. The second field in the dictionary is the 'definition', which
        is a string describing the linkrole. The final element in the list is a
        list which defines the root concept in the DAG.

        Args:
            linkrole_list: List containing Arelle representation of linkrole.
            concept_dict: Dictionary mapping concept names to ModelConcept objects.
        """
        if linkrole_list[0] != "linkRole":
            raise ValueError("First element should be 'linkRole'")

        if not isinstance(linkrole_list[1], dict):
            raise TypeError("Second element should be a dict")

        return cls(
            **linkrole_list[1],
            concepts=Concept.from_list(linkrole_list[3], concept_dict),
        )

    def get_metadata(
        self, period_type: Literal["duration", "instant"]
    ) -> list[dict[str, Any]]:
        """Get metadata from all leaf nodes in :term:`Concept` tree.

        The actual output file will contain a list of metadata objects. However,
        `get_metadata` implemented for the Concept class returns a dictionary to
        allow easily removing duplicate Concepts. This method will simply convert
        this dictionary to the list expected in the JSON file.


        Args:
            period_type: Return instant or duration concepts.

        Returns:
            A list of metadata objects.
        """
        # Convert dict to list and return
        return list(self.concepts.get_metadata(period_type).values())


class Taxonomy(BaseModel):
    """Pydantic model that defines an XBRL taxonomy.

    XBRL :term:`Taxonomies <Taxonomy>` are documents which are used to
    interpret facts reported in a filing. Taxonomies are composed of
    linkroles that group concepts into fact tables. This provides the
    structure and metadata that is used for extracting XBRL data into
    a SQLite database.
    """

    roles: list[LinkRole]

    @classmethod
    def from_source(
        cls,
        taxonomy_source: Path | io.BytesIO,
        entry_point: Path | None = None,
    ):
        """Construct taxonomy from taxonomy URL.

        Use Arelle to parse a taxonomy from a URL or local file path. The
        structures Arelle uses to represent a taxonomy and its components are not
        well documented and unintuitive, so the structures defined here are
        instantiated and used instead.

        Args:
            taxonomy_source: Path to taxonomy or in memory archive of taxonomy.
            entry_point: Path to taxonomy entry point within archive. If not None,
                then `taxonomy` should be a path to zipfile, not a URL.
        """
        if not entry_point:
            taxonomy, view = load_taxonomy(taxonomy_source)
        else:
            if isinstance(taxonomy_source, Path):
                taxonomy_source = io.BytesIO(taxonomy_source.read_bytes())

            taxonomy, view = load_taxonomy_from_archive(taxonomy_source, entry_point)

        # Create dictionary mapping concept names to concepts
        concept_dict = {
            str(name): concept for name, concept in taxonomy.qnameConcepts.items()
        }

        roles = [
            LinkRole.from_list(role, concept_dict) for role in view.jsonObject["roles"]
        ]

        return cls(roles=roles)

    def save_metadata(self, filename: Path):
        """Write taxonomy metadata to file.

        XBRL taxonomies contain metadata that can be useful for interpreting reported
        data. This method will write some of this metadata to a json file for later
        use. For more information on the metadata being extracted, see :class:`Metadata`.

        Args:
            filename: Path to output JSON file.
        """
        from ferc_xbrl_extractor.datapackage import clean_table_names

        # Get metadata for duration tables
        duration_metadata = {
            f"{clean_table_names(role.definition)}_duration": role.get_metadata(
                "duration"
            )
            for role in self.roles
        }

        # Get metadata for instant tables
        instant_metadata = {
            f"{clean_table_names(role.definition)}_instant": role.get_metadata(
                "instant"
            )
            for role in self.roles
        }

        metadata = {**duration_metadata, **instant_metadata}

        # Write to JSON file
        with Path(filename).open(mode="w") as f:
            json.dump(metadata, f, indent=4)
