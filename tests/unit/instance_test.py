"""Test XBRL instance interface."""
import datetime
import logging
from collections import Counter

import pytest

from ferc_xbrl_extractor.instance import (
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

    instance_builder = InstanceBuilder(file, "filing")
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
                {(fact.c_id, fact.value) for fact in instance.instant_facts.get(column)}
                - fact_ids
            )
            == 0
        )

    for column, fact_ids in expected_duration_facts.items():
        assert (
            len(
                {
                    (fact.c_id, fact.value)
                    for fact in instance.duration_facts.get(column)
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
                f_id="c2f2_id",
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


def test_get_instances_wrong_path(tmp_path):
    with pytest.raises(ValueError, match="Could not find XBRL instances"):
        get_instances(tmp_path / "bogus")


def test_instances_with_dates(multi_filings):
    instance_builders = [
        InstanceBuilder(f, name=f"instance_{i}") for i, f in enumerate(multi_filings)
    ]
    instances = [ib.parse() for ib in instance_builders]

    assert instances[0].report_date == datetime.date(2021, 4, 18)
    assert instances[1].report_date == datetime.date(2021, 4, 19)
