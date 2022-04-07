"""Parse a single instance"""
from lxml import etree as ET
from pydantic import BaseModel, validator
from datetime import date
from typing import Dict, List, Optional


INSTANCE_PREFIX = "{http://www.xbrl.org/2003/instance}"
EXPLICIT_DIMENSION_PREFIX = "{http://xbrl.org/2006/xbrldi}explicitMember"
TYPED_DIMENSION_PREFIX = "{http://xbrl.org/2006/xbrldi}typedMember"
FERC_FACT_PREFIX = "{http://ferc.gov/form/2021-01-01/ferc}"


def parse(path: str):
    root = ET.parse(path)

    contexts = root.findall(f"{INSTANCE_PREFIX}context")
    facts = root.findall(f"{FERC_FACT_PREFIX}*")

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

    return context_dict, fact_dict


class Period(BaseModel):
    instant: bool
    start_date: Optional[date]
    end_date: date

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Period':
        instant = elem.find(f"{INSTANCE_PREFIX}instant")
        if instant is not None:
            return cls(instant=True, end_date=instant.text)

        return cls(
            instant=False,
            start_date=elem.find(f"{INSTANCE_PREFIX}startDate").text,
            end_date=elem.find(f"{INSTANCE_PREFIX}endDate").text,
        )


class Axis(BaseModel):
    name: str
    value: str

    @validator('name', pre=True)
    def strip_prefix(cls, name):
        return name.split(':')[1]

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Axis':
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
    identifier: str
    dimensions: List[Axis]

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Entity':
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
    """Context."""

    c_id: str
    entity: Entity
    period: Period

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Context':
        return cls(**{
            'c_id': elem.attrib['id'],
            'entity': Entity.from_xml(elem.find(f"{INSTANCE_PREFIX}entity")),
            'period': Period.from_xml(elem.find(f"{INSTANCE_PREFIX}period"))
        })

    def in_axes(self, axes: List[str]) -> bool:
        return self.entity.in_axes(axes)

    def get_context_ids(self, filing_id: int = None) -> Dict:
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
    """Fact."""

    name: str
    c_id: str
    value: Optional[str]

    @classmethod
    def from_xml(cls, elem: ET.Element) -> 'Fact':
        return cls(
            name=elem.tag.split('}')[1],
            c_id=elem.attrib['contextRef'],
            value=elem.text
        )
