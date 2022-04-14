"""Parse a single instance"""
from lxml import etree as ET
from pydantic import BaseModel, validator
from datetime import date
from typing import Dict, List, Optional


INSTANCE_PREFIX = "{http://www.xbrl.org/2003/instance}"
EXPLICIT_DIMENSION_PREFIX = "{http://xbrl.org/2006/xbrldi}explicitMember"
TYPED_DIMENSION_PREFIX = "{http://xbrl.org/2006/xbrldi}typedMember"
TAXONOMY_PREFIX = "{http://www.w3.org/1999/xlink}href"
SCHEMA_PREFIX = "{http://www.xbrl.org/2003/linkbase}schemaRef"


def parse(path: str):
    """
    Parse a single XBRL instance using XML library directly.

    Args:
        path: Path to XBRL filing.

    Returns:
        context_dict: Dictionary of contexts in filing.
        fact_dict: Dictionary of facts in filing.
        taxonomy_url: URL to taxonomy used for filing.
    """
    tree = ET.parse(path)
    root = tree.getroot()

    contexts = root.findall(f"{INSTANCE_PREFIX}context")
    facts = root.findall(f"{{{root.nsmap['ferc']}}}*")
    taxonomy_url = root.find(SCHEMA_PREFIX).attrib[TAXONOMY_PREFIX]

    context_dict = {}
    fact_dict = {}
    for context in contexts:
        new_context = Context.from_xml(context)
        context_dict[new_context.c_id] = new_context
        fact_dict[new_context.c_id] = []

    for fact in facts:
        new_fact = Fact.from_xml(fact)
        if new_fact.value is not None:
            fact_dict[new_fact.c_id].append(new_fact)

    return context_dict, fact_dict, taxonomy_url


class Period(BaseModel):
    """
    Pydantic model that defines an XBRL period.
    """

    instant: bool
    start_date: Optional[date]
    end_date: date

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Period':
        """Construct Period from XML element."""
        instant = elem.find(f"{INSTANCE_PREFIX}instant")
        if instant is not None:
            return cls(instant=True, end_date=instant.text)

        return cls(
            instant=False,
            start_date=elem.find(f"{INSTANCE_PREFIX}startDate").text,
            end_date=elem.find(f"{INSTANCE_PREFIX}endDate").text,
        )


class Axis(BaseModel):
    """
    Pydantic model that defines an XBRL Axis.
    """

    name: str
    value: str

    @validator('name', pre=True)
    def strip_prefix(cls, name):
        """Strip XML prefix from name."""
        return name.split(':')[1]

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Axis':
        """Construct Axis from XML element."""
        if elem.tag == EXPLICIT_DIMENSION_PREFIX:
            return cls(
                name=elem.attrib['dimension'],
                value=elem.text
            )

        elif elem.tag == TYPED_DIMENSION_PREFIX:
            dim = elem.getchildren()[0]
            return cls(
                name=elem.attrib['dimension'],
                value=dim.text
            )


class Entity(BaseModel):
    """
    Pydantic model that defines an XBRL Entity.
    """

    identifier: str
    dimensions: List[Axis]

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Entity':
        """Construct Entity from XML element."""
        segment = elem.find(f"{INSTANCE_PREFIX}segment")
        dim_els = segment.getchildren() if segment is not None else []

        return cls(
            identifier=elem.find(f"{INSTANCE_PREFIX}identifier").text,
            dimensions=[Axis.from_xml(child) for child in dim_els]
        )

    def in_axes(self, axes: List[str]) -> bool:
        for dim in self.dimensions:
            if dim.name not in axes:
                return False
        return True


class Context(BaseModel):
    """
    Pydantic model that defines an XBRL Context.
    """

    c_id: str
    entity: Entity
    period: Period

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Context':
        """Construct Context from XML element."""
        return cls(**{
            'c_id': elem.attrib['id'],
            'entity': Entity.from_xml(elem.find(f"{INSTANCE_PREFIX}entity")),
            'period': Period.from_xml(elem.find(f"{INSTANCE_PREFIX}period"))
        })

    def in_axes(self, axes: List[str]) -> bool:
        """
        Helper function to check if a context falls within axes.

        Args:
            axes: List of axes to verify against.
        """
        return self.entity.in_axes(axes)

    def get_context_ids(self, filing_id: int = None) -> Dict:
        """Return a dictionary that defines context."""
        axes_dict = {axis.name: axis.value for axis in self.entity.dimensions}

        if filing_id is not None:
            axes_dict["filing_id"] = filing_id

        return {
            "context_id": self.c_id,
            "entity_id": self.entity.identifier,
            "start_date": self.period.start_date,
            "end_date": self.period.end_date,
            "instant": self.period.instant,
            **axes_dict
        }


class Fact(BaseModel):
    """
    Pydantic model that defines an XBRL Context.
    """

    name: str
    c_id: str
    value: Optional[str]

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Fact':
        """Construct Fact from XML element."""
        return cls(
            name=elem.tag.split('}')[1],
            c_id=elem.attrib['contextRef'],
            value=elem.text
        )
