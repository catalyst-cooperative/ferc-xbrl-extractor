"""Test XBRL instance interface."""
import logging

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
def test_context(context, axes):
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
