"""XBRL prototype structures."""
from typing import Dict, ForwardRef, List, Literal

from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept, ModelType
from pydantic import AnyHttpUrl, BaseModel

from .arelle_interface import load_taxonomy, save_references

Concept = ForwardRef("Concept")
ConceptDict = Dict[str, ModelConcept]


class XBRLType(BaseModel):
    """
    Pydantic model that defines the type of a Concept.

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
    def from_arelle_type(cls, arelle_type: ModelType):
        """Construct XBRLType class from arelle ModelType."""
        return cls(name=arelle_type.name, base=arelle_type.baseXsdType.lower())

    def get_pandas_type(self):
        """
        Return corresponding pandas type.

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

    def get_schema_type(self):
        """Return string specifying type for schema."""
        if self.base == "gyear":
            return "year"
        elif self.base == "decimal":
            return "number"
        else:
            return self.base


class Concept(BaseModel):
    """
    Pydantic model that defines an XBRL taxonomy Concept.

    A Concept in the XBRL context can represent either a single fact or a
    'container' for multiple facts. If child_concepts is empty, that indicates
    that the Concept is a single fact.
    """

    name: str
    standard_label: str
    documentation: str
    type: XBRLType  # noqa: A003
    period_type: Literal["duration", "instant"]
    child_concepts: List[Concept]

    @classmethod
    def from_list(cls, concept_list: List, concept_dict: ConceptDict):
        """
        Construct a Concept from a list.

        The way Arelle depicts the structure of the
        of a taxonomy is a bit unintuitive, but a concept will be represented as a
        list with the first element being the string 'concept', and the second two
        being dictionaries containing relevant information.
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
    """
    Pydantic model that defines an XBRL taxonomy linkrole.

    In XBRL taxonomies, Link Roles are used to group Concepts together in a
    meaningful way. These groups are often referred to as "Fact Tables". A
    Link Role contains a Directed Acyclic Graph (DAG) of concepts, which defines
    relationships.
    """

    role: AnyHttpUrl
    definition: str
    concepts: Concept

    @classmethod
    def from_list(cls, linkrole_list: List, concept_dict: ConceptDict) -> "LinkRole":
        """
        Construct from list.

        The way Arelle depicts the structure of the
        of a taxonomy is a bit unintuitive, but a Link Role will be represented as a
        list with the first element being the string 'linkRole', the second being
        dictionaries containing relevant information, then a list which defines
        the root concept in the DAG.
        """
        if linkrole_list[0] != "linkRole":
            raise ValueError("First element should be 'linkRole'")

        if not isinstance(linkrole_list[1], dict):
            raise TypeError("Second element should be dicts")

        return cls(
            **linkrole_list[1],
            concepts=Concept.from_list(linkrole_list[3], concept_dict),
        )


class Taxonomy(BaseModel):
    """
    Pydantic model that defines an XBRL taxonomy.

    A Taxonomy is an XBRL document, which is used to interpret/validate the facts in
    individual filings.
    """

    roles: List["LinkRole"]

    @classmethod
    def from_path(cls, path: str, metadata_fname: str = ""):
        """Construct taxonomy from taxonomy URL."""
        taxonomy, view = load_taxonomy(path)

        # Create dictionary mapping concept names to concepts (also strips prefix from name)
        concept_dict = {
            str(name): concept for name, concept in taxonomy.qnameConcepts.items()
        }

        # References provide sometimes useful metadata that can be saved in JSON
        if metadata_fname:
            save_references(metadata_fname, concept_dict)

        roles = [
            LinkRole.from_list(role, concept_dict) for role in view.jsonObject["roles"]
        ]

        return cls(roles=roles)
