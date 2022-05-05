"""Test XBRL instance interface."""
import logging
from datetime import date

import pytest

from xbrl_extract.instance import Context, DimensionType

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "context,axes",
    [
        (
            {
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
            },
            ["dimension_1", "dimension_2", "dimension_3"],
        )
    ],
)
def test_context_dimensions(context, axes):
    """Test Context class and verifying dimensions."""
    context = Context(**context)

    assert context.check_dimensions(axes)

    # Add an extra dimension (should fail)
    assert not context.check_dimensions(axes + ["extra_dimension"])

    # Remove dimension (should fail)
    assert not context.check_dimensions(axes[1:])

    # Change a dimension name
    axes[0] = "bogus_dimension"
    assert not context.check_dimensions(axes)


@pytest.mark.parametrize(
    "context_dict,axes",
    [
        (
            {
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
            },
            ["dimension_1", "dimension_2", "dimension_3"],
        )
    ],
)
def test_context_ids(context_dict, axes):
    """Test generation of context id dictionary."""
    context = Context(**context_dict)
    context_ids = context.get_context_ids("filing_name")

    assert context_ids.get("context_id") == "c-01"
    assert context_ids.get("entity_id") == "fake_id"
    assert context_ids.get("filing_name") == "filing_name"
    assert context_ids.get("date") == date.fromisoformat("2020-01-01")

    # Change context to have a duration period, then change
    context_dict["period"]["instant"] = False
    context_dict["period"]["start_date"] = "2019-01-01"

    context = Context(**context_dict)
    context_ids = context.get_context_ids("filing_name")

    assert context_ids.get("start_date") == date.fromisoformat("2019-01-01")
    assert context_ids.get("end_date") == date.fromisoformat("2020-01-01")
