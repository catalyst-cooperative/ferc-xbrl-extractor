"""XBRL prototype structures."""
from typing import Dict, ForwardRef, List, Optional, Set

from arelle.ModelInstanceObject import ModelFact
from arelle import Cntlr, ModelManager, ModelXbrl, XbrlConst
from arelle.ViewFileRelationshipSet import ViewRelationshipSet

from pydantic import BaseModel, root_validator, validator, AnyHttpUrl


Concept = ForwardRef('Concept')


class Concept(BaseModel):
    """Concept."""

    name: str
    label: str
    references: Optional[str]
    label: str
    type: str  # noqa: A003
    child_concepts: Optional[List[Concept]] = None

    @root_validator(pre=True)
    def map_label(cls, values):
        """Change label name."""
        if 'pref.Label' in values:
            values['label'] = values.pop('pref.Label')

        return values

    @classmethod
    def from_list(cls, concept_list: List):
        """Construct from list."""
        if concept_list[0] != 'concept':
            raise ValueError("First element should be 'concept'")

        if not isinstance(concept_list[1], dict) or not isinstance(concept_list[2], dict):
            raise TypeError("Second 2 elements should be dicts")

        return cls(
            **concept_list[1], **concept_list[2],
            child_concepts=[Concept.from_list(concept) for concept in concept_list[3:]]
        )


Concept.update_forward_refs()


class LinkRole(BaseModel):
    """LinkRole."""

    role: AnyHttpUrl
    definition: str
    concepts: 'Concept'

    @classmethod
    def from_list(cls, linkrole_list: List) -> 'Concept':
        """Construct from list."""
        if linkrole_list[0] != 'linkRole':
            raise ValueError("First element should be 'linkRole'")

        if not isinstance(linkrole_list[1], dict):
            raise TypeError("Second element should be dicts")

        return cls(**linkrole_list[1], concepts=Concept.from_list(linkrole_list[3]))


class Taxonomy(BaseModel):
    """Taxonomy."""

    roles: List['LinkRole']

    @validator('roles', pre=True)
    def validate_taxonomy(cls, roles):
        """Create children."""
        taxonomy = [LinkRole.from_list(role) for role in roles]
        return taxonomy

    def get_page(self, page_num: int, section: str = None) -> List[LinkRole]:
        """Helper to get tables from page."""
        roles = []
        page_id = str(page_num).zfill(3)
        if section:
            page_id += section

        for role in self.roles:
            if role.definition.startswith(page_id):
                roles.append(role)

        return roles

    @classmethod
    def from_path(cls, path: str):
        model_manager = ModelManager.initialize(Cntlr.Cntlr())
        xbrl = ModelXbrl.load(model_manager, path)
        view = ViewRelationshipSet(xbrl, "taxonomy.json", "roles", None, None, None)
        view.view(XbrlConst.parentChild, None, None, None)

        return cls(**view.jsonObject)
