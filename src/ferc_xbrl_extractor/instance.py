"""Parse a single instance."""
import io
from enum import Enum, auto
from typing import BinaryIO, Dict, List, Optional, Union

from lxml import etree  # nosec: B410
from lxml.etree import _Element as Element  # nosec: B410
from pydantic import BaseModel, validator

XBRL_INSTANCE = "http://www.xbrl.org/2003/instance"


class Instance:
    """Class to manage parsing XBRL filings."""

    def __init__(self, file_info: Union[str, BinaryIO], name: str):
        """
        Construct Instance class.

        Args:
            file_info: Either path to filing, or file data.
            name: Name of filing.
        """
        self.name = name
        self.file = file_info

    def parse(self, fact_prefix: str = "ferc"):
        """
        Parse a single XBRL instance using XML library directly.

        Args:
            fact_prefix: Prefix to identify facts in filing (defaults to 'ferc').

        Returns:
            context_dict: Dictionary of contexts in filing.
            fact_dict: Dictionary of facts in filing.
            filing_name: Name of filing.
        """
        # Create parser to enable parsing 'huge' xml files
        parser = etree.XMLParser(huge_tree=True)

        # Check if instance contains path to file or file data and parse accordingly
        if isinstance(self.file, str):
            tree = etree.parse(self.file, parser=parser)  # nosec: B320
            root = tree.getroot()
        elif isinstance(self.file, io.BytesIO):
            root = etree.fromstring(self.file.read(), parser=parser)  # nosec: B320
        else:
            raise TypeError("Can only parse XBRL from path to file or file like object")

        context_dict = {}
        fact_dict = {}

        contexts = root.findall(f"{{{XBRL_INSTANCE}}}context")
        facts = root.findall(f"{fact_prefix}:*", root.nsmap)

        for context in contexts:
            new_context = Context.from_xml(context)
            context_dict[new_context.c_id] = new_context
            fact_dict[new_context.c_id] = []

        for fact in facts:
            new_fact = Fact.from_xml(fact)
            if new_fact.value is not None:
                fact_dict[new_fact.c_id].append(new_fact)

        return context_dict, fact_dict, self.name


class Period(BaseModel):
    """
    Pydantic model that defines an XBRL period.

    A period can be instantaneous or a duration of time.
    """

    instant: bool
    start_date: Optional[str]
    end_date: str

    @classmethod
    def from_xml(cls, elem: Element) -> "Period":
        """Construct Period from XML element."""
        instant = elem.find(f"{{{XBRL_INSTANCE}}}instant")
        if instant is not None:
            return cls(instant=True, end_date=instant.text)

        return cls(
            instant=False,
            start_date=elem.find(f"{{{XBRL_INSTANCE}}}startDate").text,
            end_date=elem.find(f"{{{XBRL_INSTANCE}}}endDate").text,
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
        if elem.tag.endswith("explicitMember"):
            return cls(
                name=elem.attrib["dimension"],
                value=elem.text,
                dimension_type=DimensionType.EXPLICIT,
            )

        elif elem.tag.endswith("typedMember"):
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
        # Segment node contains dimensions prefixed with xbrldi
        segment = elem.find(f"{{{XBRL_INSTANCE}}}segment")
        dims = segment.findall("*") if segment is not None else []

        return cls(
            identifier=elem.find(f"{{{XBRL_INSTANCE}}}identifier").text,
            dimensions=[Axis.from_xml(child) for child in dims],
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
                "entity": Entity.from_xml(elem.find(f"{{{XBRL_INSTANCE}}}entity")),
                "period": Period.from_xml(elem.find(f"{{{XBRL_INSTANCE}}}period")),
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

        # Get date based on period type
        if self.period.instant:
            date_dict = {"date": self.period.end_date}
        else:
            date_dict = {
                "start_date": self.period.start_date,
                "end_date": self.period.end_date,
            }

        return {
            "entity_id": self.entity.identifier,
            "filing_name": filing_name,
            **date_dict,
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
        # Get prefix from namespace map to strip from fact name
        prefix = f"{{{elem.nsmap[elem.prefix]}}}"
        return cls(
            name=(elem.tag.replace(prefix, "")),  # Strip prefix
            c_id=elem.attrib["contextRef"],
            value=elem.text,
        )