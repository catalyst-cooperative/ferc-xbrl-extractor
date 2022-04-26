"""XBRL prototype structures."""
from typing import ForwardRef, List, Optional

from arelle import XbrlConst
from arelle.ViewFileRelationshipSet import ViewRelationshipSet
from pydantic import AnyHttpUrl, BaseModel, root_validator, validator

from .arelle_interface import load_xbrl, save_references

Concept = ForwardRef("Concept")


class Concept(BaseModel):
    """
    Pydantic model that defines an XBRL taxonomy Concept.

    A Concept in the XBRL context can represent either a single fact or a
    'container' for multiple facts. If child_concepts is empty, that indicates
    that the Concept is a single fact.
    """

    name: str
    label: str
    references: Optional[str]
    label: str
    type: str  # noqa: A003
    child_concepts: List[Concept]

    @root_validator(pre=True)
    def map_label(cls, values):
        """Change label name."""
        if "pref.Label" in values:
            values["label"] = values.pop("pref.Label")

        return values

    @validator("name", pre=True)
    def strip_prefix(cls, name):
        return name.split(":")[1]

    @classmethod
    def from_list(cls, concept_list: List):
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

        return cls(
            **concept_list[1],
            **concept_list[2],
            child_concepts=[Concept.from_list(concept) for concept in concept_list[3:]],
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
    def from_list(cls, linkrole_list: List) -> "Concept":
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

        return cls(**linkrole_list[1], concepts=Concept.from_list(linkrole_list[3]))


class Taxonomy(BaseModel):
    """
    Pydantic model that defines an XBRL taxonomy.

    A Taxonomy is an XBRL document, which is used to interpret/validate the facts in
    individual filings.
    """

    roles: List["LinkRole"]

    @validator("roles", pre=True)
    def validate_taxonomy(cls, roles):
        """Parse all Link Roles defined in taxonomy."""
        taxonomy = [LinkRole.from_list(role) for role in roles]
        return taxonomy

    @classmethod
    def from_path(cls, path: str, metadata_fname: str = ""):
        """Construct taxonomy from taxonomy URL."""
        xbrl = load_xbrl(path)

        # Interpret structure/relationships
        view = ViewRelationshipSet(xbrl, "taxonomy.json", "roles", None, None, None)
        view.view(XbrlConst.parentChild, None, None, None)

        # References provide sometimes useful metadata that can be saved in JSON
        if metadata_fname:
            save_references(
                metadata_fname,
                {
                    str(name).split(":")[1]: concept
                    for name, concept in xbrl.qnameConcepts.items()
                },
            )

        return cls(**view.jsonObject)
