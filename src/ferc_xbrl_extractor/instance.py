"""Parse a single instance."""
import io
from enum import Enum, auto
from typing import BinaryIO

import stringcase
from lxml import etree  # nosec: B410
from lxml.etree import _Element as Element  # nosec: B410
from pydantic import BaseModel, validator

XBRL_INSTANCE = "http://www.xbrl.org/2003/instance"


class Period(BaseModel):
    """Pydantic model that defines an XBRL period.

    A period can be instantaneous or a duration of time. Instantaneous periods will
    only have the end_date field, while duration periods will have start_date, and
    end_date.
    """

    instant: bool
    start_date: str | None
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
    """Indicate dimension type.

    XBRL contains explicit (all allowable values defined in taxonomy) and typed
    (dimension with dynamic values) dimensions.
    """

    EXPLICIT = auto()
    TYPED = auto()


class Axis(BaseModel):
    """Pydantic model that defines an XBRL Axis.

    Axes (or dimensions, terms are interchangeable in XBRL) are used for identifying
    individual facts when the entity id, and period are insufficient. All axes will
    be turned into columns, and be a part of the primary key for the table they
    belong to.
    """

    name: str
    value: str = ""
    dimension_type: DimensionType

    @validator("name", pre=True)  # type: ignore
    def strip_prefix(cls, name: str):  # noqa: N805
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
                value=dim.text if dim.text else "",
                dimension_type=DimensionType.TYPED,
            )

        # If dimension is not typed or explicit raise exception
        raise ValueError("XBRL dimension not formatted correctly")


class Entity(BaseModel):
    """Pydantic model that defines an XBRL Entity.

    Entities are used to identify individual XBRL facts. An Entity should
    contain a unique identifier, as well as any dimensions defined for a
    table.
    """

    identifier: str
    dimensions: list[Axis]

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

    def check_dimensions(self, axes: list[str]) -> bool:
        """Verify that fact and Entity have equivalent dimensions."""
        if len(self.dimensions) != len(axes):
            return False

        for dim in self.dimensions:
            if dim.name not in axes:
                return False
        return True


class Context(BaseModel):
    """Pydantic model that defines an XBRL Context.

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

    def check_dimensions(self, axes: list[str]) -> bool:
        """Helper function to check if a context falls within axes.

        Args:
            axes: List of axes to verify against.
        """
        return self.entity.check_dimensions(axes)

    def as_primary_key(self, filing_name: str) -> dict[str, str]:
        """Return a dictionary that represents the context as composite primary key."""
        # Create dictionary mapping axis (column) name to value
        axes_dict = {
            stringcase.snakecase(axis.name): axis.value
            for axis in self.entity.dimensions
        }

        # Get date based on period type
        if self.period.instant:
            date_dict = {"date": self.period.end_date}
        else:
            date_dict = {
                # Ignore type because start_date will always be str if duration period
                "start_date": self.period.start_date,  # type: ignore
                "end_date": self.period.end_date,
            }

        return {
            "entity_id": self.entity.identifier,
            "filing_name": filing_name,
            **date_dict,
            **axes_dict,
        }

    def __hash__(self):
        """Just hash Context ID as it uniquely identifies contexts for an instance."""
        return hash(self.c_id)


class Fact(BaseModel):
    """Pydantic model that defines an XBRL Fact.

    A fact is a single "data point", which contains a name, value, and a Context to
    give background information.
    """

    name: str
    c_id: str
    value: str | None

    @classmethod
    def from_xml(cls, elem: Element) -> "Fact":
        """Construct Fact from XML element."""
        # Get prefix from namespace map to strip from fact name
        prefix = f"{{{elem.nsmap[elem.prefix]}}}"
        return cls(
            name=stringcase.snakecase(elem.tag.replace(prefix, "")),  # Strip prefix
            c_id=elem.attrib["contextRef"],
            value=elem.text,
        )


FactDict = dict[tuple, dict[Context, list[Fact]]]
"""Dictionary to manage lookup of facts.

Contexts provide background information necessary to interpret/identify XBRL
facts. All contexts contain the time period, and entity that the fact pertains
to. Contexts can also contain any number of other axes to further identify facts,
which are defined in the taxonomy. All facts in a single fact table will contain
the same set of axes, which is very useful when parsing an XBRL filing and
converting fact tables into SQL tables.

This class implements a mapping of Axes -> Contexts -> Facts. When constructing
a table, first we will filter to only the set of facts that have the proper set
of axes for that table. This does not necessarily mean that each fact in that
set belongs in the table, but we can check that the name of the fact matches one
of the column names in the table. By returning this set of facts as a map
between facts and their contexts, it becomes much easier to construct rows in
the table. This is because the primary key for each table is made up from the
fields in the context, so every fact that is identified by the same context, will
be in the same row in the table.
"""


class Instance:
    """Class to encapsulate a parsed instance.

    This class should be constructed using the InstanceBuilder class. Instance wraps
    the contexts and facts parsed by the InstanceBuilder, and is used to construct
    dataframes from fact tables.
    """

    def __init__(
        self,
        contexts: dict[str, Context],
        facts: dict[str, list[Fact]],
        filing_name: str,
    ):
        """Construct Instance from parsed contexts and facts.

        This will use a dictionary to map contexts and facts to the Axes defined for
        the relevant contexts. This makes it easy to identify which facts might belong
        in a specific fact table.

        Args:
            contexts: Dictionary mapping context ID to contexts.
            facts: Dictionary mapping context ID to facts.
            filing_name: Name of parsed filing.
        """
        # This is a nested dictionary of dictionaries to locate facts by context
        self.instant_facts: FactDict = {}
        self.duration_facts: FactDict = {}

        self.filing_name = filing_name

        for c_id, context in contexts.items():
            axes = tuple(
                stringcase.snakecase(dim.name) for dim in context.entity.dimensions
            )
            if context.period.instant:
                if axes not in self.instant_facts:
                    self.instant_facts[axes] = {}

                self.instant_facts[axes][context] = facts[c_id]
            else:
                if axes not in self.duration_facts:
                    self.duration_facts[axes] = {}

                self.duration_facts[axes][context] = facts[c_id]

    def get_facts(self, instant: bool, axes: list[str]) -> dict[Context, list[Fact]]:
        """Return a dictionary that maps Contexts to a list of facts for each context.

        Args:
            instant: Get facts with instant or duration period.
            axes: List of axis names defined for fact table.
        """
        if instant:
            facts = self.instant_facts.get(tuple(axes), {})
        else:
            facts = self.duration_facts.get(tuple(axes), {})

        return facts


class InstanceBuilder:
    """Class to manage parsing XBRL filings."""

    def __init__(self, file_info: str | BinaryIO, name: str):
        """Construct InstanceBuilder class.

        Args:
            file_info: Either path to filing, or file data.
            name: Name of filing.
        """
        self.name = name
        self.file = file_info

    def parse(self, fact_prefix: str = "ferc") -> Instance:
        """Parse a single XBRL instance using XML library directly.

        This will return an Instance class which wraps the data parsed from the
        filing in question.

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

        # Dictionary mapping context ID's to context structures
        context_dict = {}

        # Dictionary mapping context ID's to fact structures
        # Allows looking up all facts with a specific context ID
        fact_dict: dict[str, list[Fact]] = {}

        # Find all contexts in XML file
        contexts = root.findall(f"{{{XBRL_INSTANCE}}}context")

        # Find all facts in XML file
        facts = root.findall(f"{fact_prefix}:*", root.nsmap)

        # Loop through contexts and parse into pydantic structures
        for context in contexts:
            new_context = Context.from_xml(context)
            context_dict[new_context.c_id] = new_context
            fact_dict[new_context.c_id] = []

        # Loop through facts and parse into pydantic structures
        for fact in facts:
            new_fact = Fact.from_xml(fact)
            if new_fact.value is not None:
                fact_dict[new_fact.c_id].append(new_fact)

        return Instance(context_dict, fact_dict, self.name)
