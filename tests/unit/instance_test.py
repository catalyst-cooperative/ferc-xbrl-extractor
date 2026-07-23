"""Test XBRL instance interface."""

import datetime
import io
import json
import logging
import zipfile
from collections import Counter

import pytest
from lxml import etree  # nosec: B410

from ferc_xbrl_extractor.instance import (
    Axis,
    Context,
    DimensionType,
    Entity,
    Fact,
    Instance,
    InstanceBuilder,
    Period,
    get_instances,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def test_context():
    """Create a test Context object."""
    return Context(
        **{
            "c_id": "c-01",
            "entity": {
                "identifier": "fake_id",
                "dimensions": [
                    {
                        "name": "dimension_1",
                        "value": "value_1",
                        "dimension_type": DimensionType.EXPLICIT,
                    },
                    {
                        "name": "dimension_2",
                        "value": "value_2",
                        "dimension_type": DimensionType.EXPLICIT,
                    },
                    {
                        "name": "dimension_3",
                        "value": "value_3",
                        "dimension_type": DimensionType.EXPLICIT,
                    },
                ],
            },
            "period": {
                "instant": True,
                "start_date": None,
                "end_date": "2020-01-01",
            },
        }
    )


def test_context_dimensions(test_context):
    """Test Context class and verifying dimensions."""
    primary_key = [dim.name for dim in test_context.entity.dimensions]
    primary_key.extend(["entity_id", "date", "filing_name"])
    assert test_context.check_dimensions(primary_key)

    # Add an extra dimension (should pass)
    assert test_context.check_dimensions(primary_key + ["extra_dimension"])

    # Remove dimension (should fail)
    assert not test_context.check_dimensions(primary_key[1:])

    # Change a dimension name
    primary_key[0] = "bogus_dimension"
    assert not test_context.check_dimensions(primary_key)


def test_context_ids(test_context):
    """Test generation of context id dictionary."""
    axes = [dim.name for dim in test_context.entity.dimensions]
    context_ids = test_context.as_primary_key("filing_name", axes)

    assert context_ids.get("entity_id") == test_context.entity.identifier
    assert context_ids.get("filing_name") == "filing_name"
    assert context_ids.get("date") == test_context.period.end_date

    # Change context to have a duration period, then change
    test_context.period.instant = False
    test_context.period.start_date = "2019-01-01"

    context_ids = test_context.as_primary_key("filing_name", axes)

    assert context_ids.get("start_date") == test_context.period.start_date
    assert context_ids.get("end_date") == test_context.period.end_date


def test_context_hash(test_context):
    """Context.__hash__ is based only on c_id, not the rest of its fields."""
    same_id_different_entity = Context(
        c_id=test_context.c_id,
        entity=Entity(identifier="a_totally_different_entity", dimensions=[]),
        period=Period(instant=True, end_date="1999-12-31"),
    )
    different_id = Context(
        c_id="some-other-c-id",
        entity=test_context.entity,
        period=test_context.period,
    )

    assert hash(test_context) == hash(same_id_different_entity)
    assert hash(test_context) != hash(different_id)


def test_axis_from_xml_rejects_malformed_dimension():
    """Axis.from_xml() raises a clear error for an unrecognized dimension tag.

    Only "explicitMember" and "typedMember" tags are valid XBRL dimensions.
    """
    elem = etree.fromstring("<xbrldi:notADimension xmlns:xbrldi='fake'/>")

    with pytest.raises(ValueError, match="XBRL dimension not formatted correctly"):
        Axis.from_xml(elem)


@pytest.mark.parametrize(
    "file_fixture",
    [
        ("in_memory_filing"),
        ("temp_file_filing"),
    ],
)
def test_parse_instance(file_fixture, request):
    """Test instance parsing."""
    file = request.getfixturevalue(file_fixture)

    instance_builder = InstanceBuilder(
        file,
        "filing",
        publication_time=datetime.datetime(2023, 10, 6, 0, 0, 0),
        taxonomy_version="form-1-2022-01-01.zip",
    )
    instance = instance_builder.parse()

    expected_instant_facts = {
        "column_one": {("cid_2", "value 5"), ("cid_3", "value 7")},
        "column_two": {("cid_2", "value 6"), ("cid_3", "value 8")},
        "column_three": {("cid_2", "value 11")},
        "column_four": {("cid_2", "value 12")},
    }
    expected_duration_facts = {
        "column_one": {
            ("cid_1", "value 1"),
            ("cid_4", "value 3"),
            ("cid_5", "value 9"),
        },
        "column_two": {
            ("cid_1", "value 2"),
            ("cid_4", "value 4"),
            ("cid_5", "value 10"),
        },
    }

    # Check that all expected facts are parsed and have appropriate context id
    for column, fact_ids in expected_instant_facts.items():
        assert (
            len(
                {
                    (fact.c_id, fact.value)
                    for fact in instance.instant_facts.get(column, [])
                }
                - fact_ids
            )
            == 0
        )

    for column, fact_ids in expected_duration_facts.items():
        assert (
            len(
                {
                    (fact.c_id, fact.value)
                    for fact in instance.duration_facts.get(column, [])
                }
                - fact_ids
            )
            == 0
        )


def test_all_fact_ids():
    instant_facts = {
        "fruit": [
            Fact(name="fruit", c_id="context_1", value="apple"),
            Fact(name="fruit", c_id="context_1", value="apple"),
            Fact(name="fruit", c_id="context_2", value="banana"),
        ],
        "caveman_utterance": [
            Fact(name="caveman_utterance", c_id="context_1", value="ooga"),
            Fact(
                name="caveman_utterance",
                c_id="context_2",
                value="booga",
            ),
        ],
    }

    duration_facts = {
        "report_date": [Fact(name="report_date", c_id="context_1", value="2022-08-12")]
    }

    contexts = {
        "context_1": Context(
            c_id="context_1",
            entity=Entity(identifier="entity_1", dimensions=[]),
            period=Period(instant=True, end_date="2023-01-01"),
        ),
        "context_2": Context(
            c_id="context_2",
            entity=Entity(identifier="entity_2", dimensions=[]),
            period=Period(instant=True, end_date="2023-01-01"),
        ),
    }

    instance = Instance(
        contexts,
        instant_facts=instant_facts,
        duration_facts=duration_facts,
        filing_name="test_instance",
        taxonomy_version="form-1-2022-01-01.zip",
        publication_time=datetime.datetime(2023, 10, 20, 0, 1, 2),
    )

    assert instance.fact_id_counts == Counter(
        {
            "context_1:fruit": 2,
            "context_1:caveman_utterance": 1,
            "context_2:fruit": 1,
            "context_2:caveman_utterance": 1,
            "context_1:report_date": 1,
        }
    )


def test_report_date_falls_back_to_certifying_official_date():
    """FERC 714 filings have no report_date fact, unlike other forms.

    Instance.__init__ falls back to the certifying_official_date fact in that
    case -- reports with different publish dates sometimes share the same
    certifying official date.
    """
    duration_facts = {
        "certifying_official_date": [
            Fact(
                name="certifying_official_date",
                c_id="context_1",
                value="2022-08-12",
            )
        ]
    }
    contexts = {
        "context_1": Context(
            c_id="context_1",
            entity=Entity(identifier="entity_1", dimensions=[]),
            period=Period(instant=True, end_date="2023-01-01"),
        ),
    }

    instance = Instance(
        contexts,
        instant_facts={},
        duration_facts=duration_facts,
        filing_name="test_instance",
        taxonomy_version="form-714-2022-01-01.zip",
        publication_time=datetime.datetime(2023, 10, 20, 0, 1, 2),
    )

    assert instance.report_date == datetime.date(2022, 8, 12)


def test_get_instances_wrong_path(tmp_path):
    with pytest.raises(ValueError, match="Could not find XBRL instances"):
        get_instances(tmp_path / "bogus")


def test_get_instances_from_directory(tmp_path):
    """get_instances() supports a directory of unzipped filings with an rssfeed.

    This mirrors the zip-archive case, but reading the "rssfeed" metadata file
    and individual filings from disk instead of from inside a zip -- useful for
    local debugging, where it's convenient to edit filings directly rather than
    repackaging them into a zip after every change.
    """
    (tmp_path / "filing.xbrl").write_text("<xbrl/>")
    rssfeed = {
        "some_filer": [
            {
                "filename": "filing.xbrl",
                "rss_metadata": {"published_parsed": "2023-10-06T00:00:00+00:00"},
                "taxonomy_zip_name": "form-1-2022-01-01.zip",
            }
        ]
    }
    (tmp_path / "rssfeed").write_text(json.dumps(rssfeed))

    instance_builders = get_instances(tmp_path)

    assert len(instance_builders) == 1
    builder = instance_builders[0]
    assert isinstance(builder, InstanceBuilder)
    assert builder.name == "filing"
    assert builder.publication_time == datetime.datetime(2023, 10, 6, 0, 0, 0)
    assert builder.taxonomy_version == "form-1-2022-01-01.zip"


def test_get_instances_from_directory_missing_rssfeed(tmp_path):
    """A directory without an "rssfeed" file is rejected with a clear error."""
    (tmp_path / "filing.xbrl").write_text("<xbrl/>")

    with pytest.raises(ValueError, match="Could not find an 'rssfeed' metadata file"):
        get_instances(tmp_path)


def test_get_instances_rejects_bare_file(tmp_path):
    """get_instances() doesn't support a single bare filing.

    Unlike a directory, a single file has no room for an accompanying "rssfeed"
    metadata file, so there's no way to determine its publication_time or
    taxonomy_version.
    """
    instance_file = tmp_path / "filing.xbrl"
    instance_file.write_text("<xbrl/>")

    with pytest.raises(ValueError, match="Expected a zipfile or directory"):
        get_instances(instance_file)


def test_get_instances_from_bytesio():
    """get_instances() supports an in-memory zip archive, not just a Path.

    This is how PUDL always calls it in production (FercXbrlDatastore.get_filings
    in pudl/src/pudl/extract/xbrl.py wraps every archive in io.BytesIO before
    handing it off to this library), so it needs its own direct test rather than
    relying only on the Path-to-zip case.
    """
    rssfeed = {
        "some_filer": [
            {
                "filename": "filing.xbrl",
                "rss_metadata": {"published_parsed": "2023-10-06T00:00:00+00:00"},
                "taxonomy_zip_name": "form-1-2022-01-01.zip",
            }
        ]
    }
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, mode="w") as zf:
        zf.writestr("rssfeed", json.dumps(rssfeed))
        zf.writestr("filing.xbrl", "<xbrl/>")
    zip_bytes.seek(0)

    instance_builders = get_instances(zip_bytes)

    assert len(instance_builders) == 1
    builder = instance_builders[0]
    assert isinstance(builder, InstanceBuilder)
    assert builder.name == "filing"
    assert builder.publication_time == datetime.datetime(2023, 10, 6, 0, 0, 0)
    assert builder.taxonomy_version == "form-1-2022-01-01.zip"


def test_instances_with_dates(multi_filings):
    instance_builders = [
        InstanceBuilder(
            f,
            name=f"instance_{i}",
            publication_time=datetime.datetime(2023, 10, 6, 0, 0, 0),
            taxonomy_version="form-1-2022-01-01.zip",
        )
        for i, f in enumerate(multi_filings)
    ]
    instances = [ib.parse() for ib in instance_builders]

    assert instances[0].report_date == datetime.date(2021, 4, 18)
    assert instances[1].report_date == datetime.date(2021, 4, 19)
