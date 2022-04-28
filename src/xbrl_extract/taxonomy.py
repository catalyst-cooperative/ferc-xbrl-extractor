"""XBRL prototype structures."""
from typing import Dict, ForwardRef, List, Literal

from arelle import XbrlConst
from arelle.ModelDtsObject import ModelConcept
from pydantic import AnyHttpUrl, BaseModel

from .arelle_interface import load_taxonomy, save_references

Concept = ForwardRef("Concept")
ConceptDict = Dict[str, ModelConcept]


class Concept(BaseModel):
    """
    Pydantic model that defines an XBRL taxonomy Concept.

    A Concept in the XBRL context can represent either a single fact or a
    'container' for multiple facts. If child_concepts is empty, that indicates
    that the Concept is a single fact.
    """

    name: str
    documentation: str
    type: str  # noqa: A003
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
            documentation=concept.label(XbrlConst.documentationLabel),
            type=concept.type.name,
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
