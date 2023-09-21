"""Parse a single instance."""
import datetime
import io
import itertools
import zipfile
from collections import Counter, defaultdict
from enum import Enum, auto
from pathlib import Path
from typing import BinaryIO

import stringcase
from lxml import etree  # nosec: B410
from lxml.etree import _Element as Element  # nosec: B410
from pydantic import BaseModel, validator

from ferc_xbrl_extractor.helpers import get_logger

XBRL_INSTANCE = "http://www.xbrl.org/2003/instance"


class Period(BaseModel):
    """Pydantic model that defines an XBRL period.

    A period can be instantaneous or a duration of time. Instantaneous periods will
    only have the end_date field, while duration periods will have start_date, and
    end_date.
    """

    instant: bool
    start_date: str | None = None
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

    @validator("name", pre=True)
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

        if elem.tag.endswith("typedMember"):
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

    def check_dimensions(self, primary_key: list[str]) -> bool:
        """Check if Context has extra axes not defined in primary key."""
        for dim in self.dimensions:
            if stringcase.snakecase(dim.name) not in primary_key:
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

    def check_dimensions(self, primary_key: list[str]) -> bool:
        """Check if Context has extra axes not defined in primary key.

        Facts missing axes from primary key can be treated as totals
        across that axis, but facts with extra axes would not fit in
        table.

        Args:
            primary_key: Primary key of table.
        """
        return self.entity.check_dimensions(primary_key)

    def as_primary_key(self, filing_name: str, axes: list[str]) -> dict[str, str]:
        """Return a dictionary that represents the context as composite primary key."""
        # Create dictionary mapping axis (column) name to value
        axes_dict = {
            stringcase.snakecase(axis.name): axis.value
            for axis in self.entity.dimensions
        }
        axes_dict |= {axis: "total" for axis in axes if axis not in axes_dict}

        # Get date based on period type
        if self.period.instant:
            date_dict = {"date": self.period.end_date}
        else:
            date_dict = {
                # Ignore type because start_date will always be str if duration period
                "start_date": self.period.start_date,
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

    # TODO (daz): use computed_field once we upgrade to Pydantic 2.x
    def f_id(self) -> str:
        """A unique identifier for the Fact.

        There is an `id` attribute on most fact entries, but there are some
        facts without an `id` attribute, so we can't use that. Instead we
        assume that each fact is uniquely identified by its context ID and the
        concept name.

        NB, this is a function, not a property. This would be a property, but a
        property is not pickleable within Pydantic 1.x
        """
        return f"{self.c_id}:{self.name}"


class Instance:
    """Class to encapsulate a parsed instance.

    This class should be constructed using the InstanceBuilder class. Instance wraps
    the contexts and facts parsed by the InstanceBuilder, and is used to construct
    dataframes from fact tables.
    """

    def __init__(
        self,
        contexts: dict[str, Context],
        instant_facts: dict[str, list[Fact]],
        duration_facts: dict[str, list[Fact]],
        filing_name: str,
    ):
        """Construct Instance from parsed contexts and facts.

        This will use a dictionary to map contexts and facts to the Axes defined for
        the relevant contexts. This makes it easy to identify which facts might belong
        in a specific fact table.

        Args:
            contexts: Dictionary mapping context ID to contexts.
            instant_facts: Dictionary mapping concept name to list of instant facts.
            duration_facts: Dictionary mapping concept name to list of duration facts.
            filing_name: Name of parsed filing.
        """
        self.logger = get_logger(__name__)
        self.instant_facts = instant_facts
        self.duration_facts = duration_facts
        self.fact_id_counts = Counter(
            f.f_id()
            for f in itertools.chain.from_iterable(
                (instant_facts | duration_facts).values()
            )
        )
        self.total_facts = len(self.fact_id_counts)
        self.duplicated_fact_ids = [
            f_id
            for f_id, _ in itertools.takewhile(
                lambda c: c[1] >= 2, self.fact_id_counts.most_common()
            )
        ]
        if self.duplicated_fact_ids:
            self.logger.debug(
                f"Duplicated facts in {filing_name}: {self.duplicated_fact_ids}"
            )
        self.used_fact_ids: set[str] = set()

        self.filing_name = filing_name
        self.contexts = contexts
        if "report_date" in duration_facts:
            self.report_date = datetime.date.fromisoformat(
                duration_facts["report_date"][0].value
            )
        else:
            # FERC 714 workaround - though sometimes reports with different
            # publish dates have the same certifying official date.
            self.report_date = datetime.date.fromisoformat(
                duration_facts["certifying_official_date"][0].value
            )

    def get_facts(
        self, instant: bool, concept_names: list[str], primary_key: list[str]
    ) -> dict[str, list[Fact]]:
        """Return a dictionary that maps Context ID's to a list of facts for each context.

        Args:
            instant: Get facts with instant or duration period.
            concept_names: Name of concepts which map to a column name and name of facts.
            primary_key: Name of columns in primary_key used to filter facts.
        """
        period_fact_dict = self.instant_facts if instant else self.duration_facts

        all_facts_for_concepts = itertools.chain.from_iterable(
            period_fact_dict[concept_name] for concept_name in concept_names
        )
        return (
            fact
            for fact in all_facts_for_concepts
            if self.contexts[fact.c_id].check_dimensions(primary_key)
        )


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
        tree = etree.parse(self.file, parser=parser)  # noqa: S320
        root = tree.getroot()

        # Dictionary mapping context ID's to context structures
        context_dict = {}

        # Dictionary mapping context ID's to fact structures
        # Allows looking up all facts with a specific context ID
        instant_facts: dict[str, list[Fact]] = defaultdict(list)
        duration_facts: dict[str, list[Fact]] = defaultdict(list)

        # Find all contexts in XML file
        contexts = root.findall(f"{{{XBRL_INSTANCE}}}context")

        # Find all facts in XML file
        facts = root.findall(f"{fact_prefix}:*", root.nsmap)

        # Loop through contexts and parse into pydantic structures
        for context in contexts:
            new_context = Context.from_xml(context)
            context_dict[new_context.c_id] = new_context

        # Loop through facts and parse into pydantic structures
        for fact in facts:
            new_fact = Fact.from_xml(fact)

            # Sort facts by period type
            if new_fact.value is not None:
                if context_dict[new_fact.c_id].period.instant:
                    instant_facts[new_fact.name].append(new_fact)
                else:
                    duration_facts[new_fact.name].append(new_fact)

        return Instance(context_dict, instant_facts, duration_facts, self.name)


def instances_from_zip(instance_path: Path | io.BytesIO) -> list[InstanceBuilder]:
    """Get list of instances from specified path to zipfile.

    Args:
        instance_path: Path to zipfile containing XBRL filings.
    """
    allowable_suffixes = [".xbrl"]

    archive = zipfile.ZipFile(instance_path)

    # Read files into in memory buffers to parse
    return [
        InstanceBuilder(
            io.BytesIO(archive.open(filename).read()), filename.split(".")[0]
        )
        for filename in archive.namelist()
        if Path(filename).suffix in allowable_suffixes
    ]


def get_instances(instance_path: Path | io.BytesIO) -> list[InstanceBuilder]:
    """Get list of instances from specified path.

    Args:
        instance_path: Path to one or more XBRL filings.
    """
    allowable_suffixes = [".xbrl"]

    if isinstance(instance_path, io.BytesIO):
        return instances_from_zip(instance_path)

    if not instance_path.exists():
        raise ValueError(f"Could not find XBRL instances at {instance_path}.")

    if instance_path.suffix == ".zip":
        return instances_from_zip(instance_path)

    # Single instance
    if instance_path.is_file():
        instances = [instance_path]
    # Directory of instances
    else:
        # Must be either a directory or file
        assert instance_path.is_dir()  # nosec: B101
        instances = sorted(instance_path.iterdir())

    return [
        InstanceBuilder(str(instance), instance.name.rstrip(instance.suffix))
        for instance in sorted(instances)
        if instance.suffix in allowable_suffixes
    ]
