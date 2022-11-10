"""XBRL prototype structures."""
from typing import Dict, Literal

import pydantic
from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept, ModelType
from pydantic import AnyHttpUrl, BaseModel

from ferc_xbrl_extractor.arelle_interface import (
    extract_metadata,
    load_taxonomy,
    load_taxonomy_from_archive,
)

ConceptDict = Dict[str, ModelConcept]


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

    def get_pandas_type(self) -> str:
        """Return corresponding pandas type.

        Gets a string representation of the pandas type best suited to represent the
        base type.
        """
        if self.base == "string" or self.base == "date" or self.base == "duration":
            return "string"
        elif self.base == "decimal":
            return "Float64"
        elif self.base == "gyear" or self.base == "integer":
            return "Int64"
        elif self.base == "boolean":
            return "boolean"

    def get_schema_type(self) -> str:
        """Return string specifying type for a frictionless table schema."""
        if self.base == "gyear":
            return "year"
        elif self.base == "decimal":
            return "number"
        elif self.base == "duration":
            return "string"
        else:
            return self.base


class Concept(BaseModel):
    """Pydantic model that defines an XBRL taxonomy Concept.

    A Concept in the XBRL context can represent either a single fact or a
    'container' for multiple facts. If child_concepts is empty, that indicates
    that the Concept is a single fact.
    """

    name: str
    standard_label: str
    documentation: str
    type_: XBRLType = pydantic.Field(alias="type")
    period_type: Literal["duration", "instant"]
    child_concepts: "list[Concept]"

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
        )


Concept.update_forward_refs()


class LinkRole(BaseModel):
    """Pydantic model that defines an XBRL taxonomy linkrole.

    In XBRL taxonomies, Link Roles are used to group Concepts together in a
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


class Taxonomy(BaseModel):
    """Pydantic model that defines an XBRL taxonomy.

    XBRL Taxonomies are documents which are used to interpret facts reported in a
    filing. Taxonomies are composed of linkroles that group concepts into fact
    tables. This provides the structure and metadata that is used for extracting
    XBRL data into a SQLite database.
    """

    roles: list[LinkRole]

    @classmethod
    def from_path(
        cls,
        path: str,
        archive_file_path: str | None = None,
        metadata_path: str | None = None,
    ):
        """Construct taxonomy from taxonomy URL.

        Use Arelle to parse a taxonomy from a URL or local file path. The
        structures Arelle uses to represent a taxonomy and its components are not
        well documented and unintuitive, so the structures defined here are
        instantiated and used instead.

        Args:
            path: URL or local path to taxonomy.
            archive_file_path: Path to taxonomy entry point within archive. If not None,
                then `taxonomy` should be a path to zipfile, not a URL.
            metadata_path: Path to metadata json file to output taxonomy metadata.
        """
        if not archive_file_path:
            taxonomy, view = load_taxonomy(path)
        else:
            taxonomy, view = load_taxonomy_from_archive(path, archive_file_path)

        # Create dictionary mapping concept names to concepts
        concept_dict = {
            str(name): concept for name, concept in taxonomy.qnameConcepts.items()
        }

        # Extract metadata to json file if requested
        if metadata_path:
            extract_metadata(metadata_path, concept_dict)

        roles = [
            LinkRole.from_list(role, concept_dict) for role in view.jsonObject["roles"]
        ]

        return cls(roles=roles)
