"""Parse a single instance."""

import datetime
import io
import itertools
import json
import logging
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator
from enum import Enum, auto
from functools import cached_property
from pathlib import Path
from typing import BinaryIO

import stringcase
from lxml import etree  # nosec: B410
from lxml.etree import _Element as Element  # nosec: B410
from pydantic import BaseModel, field_validator

from ferc_xbrl_extractor.helpers import get_logger

XBRL_INSTANCE = "http://www.xbrl.org/2003/instance"
XBRL_LINK = "http://www.xbrl.org/2003/linkbase"


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
            assert instant.text is not None
            return cls(instant=True, end_date=instant.text)

        start_date_elem = elem.find(f"{{{XBRL_INSTANCE}}}startDate")
        end_date_elem = elem.find(f"{{{XBRL_INSTANCE}}}endDate")
        assert start_date_elem is not None
        assert end_date_elem is not None
        assert end_date_elem.text is not None
        return cls(
            instant=False,
            start_date=start_date_elem.text,
            end_date=end_date_elem.text,
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

    @field_validator("name", mode="before")
    @classmethod
    def strip_prefix(cls, name: str) -> str:
        """Strip XML prefix from name."""
        return name.split(":")[1] if ":" in name else name

    @classmethod
    def from_xml(cls, elem: Element) -> "Axis":
        """Construct Axis from XML element."""
        # A parsed element's tag is always a plain str; only an as-yet-unparsed,
        # freshly-constructed element could have a QName tag instead.
        assert isinstance(elem.tag, str)
        if elem.tag.endswith("explicitMember"):
            return cls(
                name=elem.attrib["dimension"],
                value=elem.text or "",
                dimension_type=DimensionType.EXPLICIT,
            )

        if elem.tag.endswith("typedMember"):
            dim = elem[0]
            return cls(
                name=elem.attrib["dimension"],
                value=dim.text or "",
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

        identifier_elem = elem.find(f"{{{XBRL_INSTANCE}}}identifier")
        assert identifier_elem is not None
        assert identifier_elem.text is not None

        return cls(
            identifier=identifier_elem.text,
            dimensions=[Axis.from_xml(child) for child in dims],
        )

    @cached_property
    def snakecase_dimensions(self) -> list[str]:
        """Return list of dimension names in snakecase."""
        return [stringcase.snakecase(dim.name) for dim in self.dimensions]

    def check_dimensions(self, primary_key: list[str]) -> bool:
        """Check if Context has extra axes not defined in primary key."""
        return all(snake_dim in primary_key for snake_dim in self.snakecase_dimensions)


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
        entity_elem = elem.find(f"{{{XBRL_INSTANCE}}}entity")
        period_elem = elem.find(f"{{{XBRL_INSTANCE}}}period")
        assert entity_elem is not None
        assert period_elem is not None
        return cls(
            c_id=elem.attrib["id"],
            entity=Entity.from_xml(entity_elem),
            period=Period.from_xml(period_elem),
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
            # start_date is always populated for duration periods -- see Period.from_xml.
            assert self.period.start_date is not None
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
    value: str | None = None

    @classmethod
    def from_xml(cls, elem: Element) -> "Fact":
        """Construct Fact from XML element."""
        # Get prefix from namespace map to strip from fact name
        prefix = f"{{{elem.nsmap[elem.prefix]}}}"
        # A parsed element's tag is always a plain str; only an as-yet-unparsed,
        # freshly-constructed element could have a QName tag instead.
        assert isinstance(elem.tag, str)
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
        publication_time: datetime.datetime,
        taxonomy_version: str,
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
            publication_time: the time at which the filing was made available online.
        """
        self.logger: logging.Logger = get_logger(__name__)
        self.taxonomy_version: str = taxonomy_version
        self.instant_facts: dict[str, list[Fact]] = instant_facts
        self.duration_facts: dict[str, list[Fact]] = duration_facts
        self.fact_id_counts: Counter[str] = Counter(
            f.f_id()
            for f in itertools.chain.from_iterable(
                (instant_facts | duration_facts).values()
            )
        )
        self.total_facts: int = len(self.fact_id_counts)
        self.duplicated_fact_ids: list[str] = [
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

        self.filing_name: str = filing_name
        self.contexts: dict[str, Context] = contexts
        if "report_date" in duration_facts:
            report_date_value = duration_facts["report_date"][0].value
            assert report_date_value is not None
            self.report_date: datetime.date = datetime.date.fromisoformat(
                report_date_value
            )
        else:
            # FERC 714 workaround - though sometimes reports with different
            # publish dates have the same certifying official date.
            certifying_official_date_value = duration_facts["certifying_official_date"][
                0
            ].value
            assert certifying_official_date_value is not None
            self.report_date: datetime.date = datetime.date.fromisoformat(
                certifying_official_date_value
            )
        self.publication_time: datetime.datetime = publication_time

    def get_facts(
        self, instant: bool, concept_names: list[str], primary_key: list[str]
    ) -> Iterator[Fact]:
        """Return facts for the requested concepts whose context matches primary_key.

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

    def __init__(
        self,
        file_info: str | BinaryIO,
        name: str,
        publication_time: datetime.datetime,
        taxonomy_version: str,
    ):
        """Construct InstanceBuilder class.

        Args:
            file_info: Either path to filing, or file data.
            name: Name of filing.
            publication_time: Time this filing was published.
        """
        self.name: str = name
        self.file: str | BinaryIO = file_info
        self.publication_time: datetime.datetime = publication_time
        self.taxonomy_version: str = taxonomy_version

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

        # Find all facts in XML file. Filter out the default-namespace entry (key
        # None) since it's not needed to match the always-prefixed fact_prefix:*
        # expression below, and lxml-stubs types the namespaces mapping as str-keys
        # only even though lxml itself accepts a None key at runtime.
        nsmap = {
            prefix: uri for prefix, uri in root.nsmap.items() if prefix is not None
        }
        facts = root.findall(f"{fact_prefix}:*", nsmap)

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

        return Instance(
            contexts=context_dict,
            instant_facts=instant_facts,
            duration_facts=duration_facts,
            filing_name=self.name,
            publication_time=self.publication_time,
            taxonomy_version=self.taxonomy_version,
        )


def _parse_rssfeed_metadata(
    raw: bytes,
) -> tuple[dict[str, datetime.datetime], dict[str, str]]:
    """Parse an "rssfeed" metadata file into publication times and taxonomy versions.

    Shared by instances_from_zip and instances_from_directory, which differ only
    in where they read the "rssfeed" file and individual filings from.
    """
    filings_metadata = json.loads(raw)

    # Publication time is always published as UTC, but just to be safe convert to UTC
    # then make timezone naive
    publication_times = {
        filing["filename"]: datetime.datetime.fromisoformat(
            filing["rss_metadata"]["published_parsed"]
        )
        .astimezone(datetime.UTC)
        .replace(tzinfo=None)
        for filers_metadata in filings_metadata.values()
        for filing in filers_metadata
    }
    taxonomy_versions = {
        filing["filename"]: filing["taxonomy_zip_name"]
        for filers_metadata in filings_metadata.values()
        for filing in filers_metadata
    }
    return publication_times, taxonomy_versions


def instances_from_zip(instance_path: Path | io.BytesIO) -> list[InstanceBuilder]:
    """Get list of instances from specified path to zipfile.

    Args:
        instance_path: Path to zipfile containing XBRL filings.
    """
    allowable_suffixes = [".xbrl"]

    archive = zipfile.ZipFile(instance_path)

    with archive.open("rssfeed") as f:
        publication_times, taxonomy_versions = _parse_rssfeed_metadata(f.read())

    # Read files into in memory buffers to parse
    return [
        InstanceBuilder(
            io.BytesIO(archive.open(filename).read()),
            Path(filename).stem,
            publication_time=publication_times[filename],
            taxonomy_version=taxonomy_versions[filename],
        )
        for filename in archive.namelist()
        if Path(filename).suffix in allowable_suffixes
    ]


def instances_from_directory(instance_path: Path) -> list[InstanceBuilder]:
    """Get list of instances from a directory of unzipped XBRL filings.

    Mainly useful for local debugging, where it's convenient to edit filings
    directly on disk rather than repackaging them into a zip after every change.
    The directory must still include the "rssfeed" metadata file that FERC's
    archiving process bundles into the zip alongside the filings -- e.g. by
    unzipping one of these archives without discarding it -- since that's the
    only source for each filing's publication_time and taxonomy_version. See
    instances_from_zip for the zip-archive equivalent of this function.

    Args:
        instance_path: Path to a directory of XBRL filings, including an
            "rssfeed" metadata file.
    """
    allowable_suffixes = [".xbrl"]

    rssfeed_path = instance_path / "rssfeed"
    if not rssfeed_path.exists():
        raise ValueError(
            f"Could not find an 'rssfeed' metadata file in {instance_path}. "
            "get_instances() expects a directory of XBRL filings to include "
            "the 'rssfeed' file bundled by FERC's archiving process -- see "
            "its docstring."
        )
    publication_times, taxonomy_versions = _parse_rssfeed_metadata(
        rssfeed_path.read_bytes()
    )

    return [
        InstanceBuilder(
            str(instance),
            instance.stem,
            publication_time=publication_times[instance.name],
            taxonomy_version=taxonomy_versions[instance.name],
        )
        for instance in sorted(instance_path.iterdir())
        if instance.suffix in allowable_suffixes
    ]


def get_instances(instance_path: Path | io.BytesIO) -> list[InstanceBuilder]:
    """Get list of instances from a zipfile or directory of XBRL filings.

    Both a zip archive (or in-memory equivalent) and a plain directory are
    supported, as long as an "rssfeed" metadata file is present -- FERC's
    archiving process bundles one into every zip archive automatically, and
    it's still there if you unzip one without discarding it. Each filing's
    publication_time and taxonomy_version are derived from that file; without
    it there's no reliable way to determine them, which is why a bare single
    filing (with no "rssfeed" of its own) isn't supported.

    Args:
        instance_path: Path to a zipfile or directory of XBRL filings, or an
            in-memory zip archive.
    """
    if isinstance(instance_path, io.BytesIO):
        return instances_from_zip(instance_path)

    if not instance_path.exists():
        raise ValueError(f"Could not find XBRL instances at {instance_path}.")

    if instance_path.suffix == ".zip":
        return instances_from_zip(instance_path)

    if instance_path.is_dir():
        return instances_from_directory(instance_path)

    raise ValueError(
        f"Expected a zipfile or directory of XBRL filings, got {instance_path}. "
        "get_instances() only supports those two input types -- see its docstring."
    )
