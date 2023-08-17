"""Test XBRL instance interface."""
import logging

import pytest

from ferc_xbrl_extractor.instance import Context, DimensionType

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
