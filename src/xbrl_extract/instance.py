"""Parse a single instance."""
from datetime import date
from enum import Enum, auto
from typing import Dict, List, Optional
from xml.etree.ElementTree import Element  # nosec: B405

from defusedxml import ElementTree
from pydantic import BaseModel, validator

INSTANCE_PREFIX = "{http://www.xbrl.org/2003/instance}"  # noqa: FS003
EXPLICIT_DIMENSION_PREFIX = "{http://xbrl.org/2006/xbrldi}explicitMember"  # noqa: FS003
TYPED_DIMENSION_PREFIX = "{http://xbrl.org/2006/xbrldi}typedMember"  # noqa: FS003
TAXONOMY_PREFIX = "{http://www.w3.org/1999/xlink}href"  # noqa: FS003
SCHEMA_PREFIX = "{http://www.xbrl.org/2003/linkbase}schemaRef"  # noqa: FS003


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
    tree = ElementTree.parse(path)
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

    A period can be instantaneous or a duration of time.
    """

    instant: bool
    start_date: Optional[date]
    end_date: date

    @classmethod
    def from_xml(cls, elem: Element) -> "Period":
        """Construct Period from XML element."""
        instant = elem.find(f"{INSTANCE_PREFIX}instant")
        if instant is not None:
            return cls(instant=True, end_date=instant.text)

        return cls(
            instant=False,
            start_date=elem.find(f"{INSTANCE_PREFIX}startDate").text,
            end_date=elem.find(f"{INSTANCE_PREFIX}endDate").text,
        )


class DimensionType(Enum):
    """
    Indicate dimension type.

    XBRL contains explicit (all allowable values defined in taxonomy) and typed
    (value defined in filing) dimensions.
    """

    EXPLICIT = auto()
    TYPED = auto()


class Axis(BaseModel):
    """
    Pydantic model that defines an XBRL Axis.

    Axes (or dimensions, terms are interchangeable in XBRL) are used for identifying
    individual facts when the entity id, and period are insufficient. All axes will
    be turned into columns, and be a part of the primary key for the table they
    belong to.
    """

    name: str
    value: str
    dimension_type: DimensionType

    @validator("name", pre=True)
    def strip_prefix(cls, name):  # noqa: N805
        """Strip XML prefix from name."""
        return name.split(":")[1] if ":" in name else name

    @classmethod
    def from_xml(cls, elem: Element) -> "Axis":
        """Construct Axis from XML element."""
        if elem.tag == EXPLICIT_DIMENSION_PREFIX:
            return cls(
                name=elem.attrib["dimension"],
                value=elem.text,
                dimension_type=DimensionType.EXPLICIT,
            )

        elif elem.tag == TYPED_DIMENSION_PREFIX:
            dim = elem.getchildren()[0]
            return cls(
                name=elem.attrib["dimension"],
                value=dim.text,
                dimension_type=DimensionType.TYPED,
            )


class Entity(BaseModel):
    """
    Pydantic model that defines an XBRL Entity.

    Entities are used to identify individual XBRL facts. An Entity should
    contain a unique identifier, as well as any dimensions defined for a
    table.
    """

    identifier: str
    dimensions: List[Axis]

    @classmethod
    def from_xml(cls, elem: Element) -> "Entity":
        """Construct Entity from XML element."""
        segment = elem.find(f"{INSTANCE_PREFIX}segment")
        dim_els = segment.getchildren() if segment is not None else []

        return cls(
            identifier=elem.find(f"{INSTANCE_PREFIX}identifier").text,
            dimensions=[Axis.from_xml(child) for child in dim_els],
        )

    def check_dimensions(self, axes: List[str]) -> bool:
        """Verify that fact and Entity have equivalent dimensions."""
        if len(self.dimensions) != len(axes):
            return False

        for dim in self.dimensions:
            if dim.name not in axes:
                return False
        return True


class Context(BaseModel):
    """
    Pydantic model that defines an XBRL Context.

    Contexts are used to provide useful background information for facts. The
    context indicates the entity, time period, and any other dimensions which apply
    to the fact.
    """

    c_id: str
    entity: Entity
    period: Period

    @classmethod
    def from_xml(cls, elem: Element) -> "Context":
        """Construct Context from XML element."""
        return cls(
            **{
                "c_id": elem.attrib["id"],
                "entity": Entity.from_xml(elem.find(f"{INSTANCE_PREFIX}entity")),
                "period": Period.from_xml(elem.find(f"{INSTANCE_PREFIX}period")),
            }
        )

    def check_dimensions(self, axes: List[str]) -> bool:
        """
        Helper function to check if a context falls within axes.

        Args:
            axes: List of axes to verify against.
        """
        return self.entity.check_dimensions(axes)

    def get_context_ids(self, filing_name: str) -> Dict:
        """Return a dictionary that defines context."""
        axes_dict = {axis.name: axis.value for axis in self.entity.dimensions}

        return {
            "context_id": self.c_id,
            "entity_id": self.entity.identifier,
            "start_date": self.period.start_date,
            "end_date": self.period.end_date,
            "instant": self.period.instant,
            "filing_name": filing_name,
            **axes_dict,
        }


class Fact(BaseModel):
    """
    Pydantic model that defines an XBRL Fact.

    A fact is a single "data point", which contains a name, value, and a Context to
    give background information.
    """

    name: str
    c_id: str
    value: Optional[str]

    @classmethod
    def from_xml(cls, elem: Element) -> "Fact":
        """Construct Fact from XML element."""
        return cls(
            name=elem.tag.split("}")[1], c_id=elem.attrib["contextRef"], value=elem.text
        )
