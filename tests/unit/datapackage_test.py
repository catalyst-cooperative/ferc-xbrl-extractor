"""Test XBRL extraction interface."""
import logging

import pytest

from ferc_xbrl_extractor.datapackage import Resource
from ferc_xbrl_extractor.taxonomy import LinkRole

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "link_role,duration_column_names,instant_column_names",
    [
        (
            {
                "role": "https://example.com",
                "definition": "001 - Schedule - Example Link Role",
                "concepts": {
                    "name": "test_concept",
                    "standard_label": "generic label",
                    "documentation": "Test concept.",
                    "type": {
                        "name": "type",
                        "base": "string",
                    },
                    "period_type": "duration",
                    "child_concepts": [
                        {
                            "name": "TestAxis",
                            "standard_label": "generic label",
                            "documentation": "Concept to test Axis",
                            "type": {
                                "name": "type",
                                "base": "string",
                            },
                            "period_type": "duration",
                            "child_concepts": [],
                        },
                        {
                            "name": "DurationConcept",
                            "standard_label": "generic label",
                            "documentation": "Test a generic duration column.",
                            "type": {"name": "type", "base": "string"},
                            "period_type": "duration",
                            "child_concepts": [],
                        },
                        {
                            "name": "DurationConceptInt",
                            "standard_label": "generic label",
                            "documentation": "Test a duration column with int type.",
                            "type": {"name": "type", "base": "integer"},
                            "period_type": "duration",
                            "child_concepts": [],
                        },
                        {
                            "name": "InstantConcept",
                            "standard_label": "generic label",
                            "documentation": "Test a generic instant column.",
                            "type": {"name": "type", "base": "string"},
                            "period_type": "instant",
                            "child_concepts": [],
                        },
                        {
                            "name": "ConceptContainer",
                            "standard_label": "generic label",
                            "documentation": "Test a concept with child concepts.",
                            "type": {"name": "type", "base": "string"},
                            "period_type": "instant",
                            "child_concepts": [
                                {
                                    "name": "ChildConcept",
                                    "standard_label": "generic label",
                                    "documentation": "Test child concept.",
                                    "type": {"name": "type", "base": "gyear"},
                                    "period_type": "instant",
                                    "child_concepts": [],
                                },
                            ],
                        },
                        {
                            "name": "ConceptBool",
                            "standard_label": "generic label",
                            "documentation": "Test a column with bool type.",
                            "type": {"name": "type", "base": "boolean"},
                            "period_type": "instant",
                            "child_concepts": [],
                        },
                    ],
                },
            },
            {
                "entity_id",
                "filing_name",
                "start_date",
                "end_date",
                "test_axis",
                "duration_concept",
                "duration_concept_int",
            },
            {
                "entity_id",
                "filing_name",
                "date",
                "test_axis",
                "instant_concept",
                "child_concept",
                "concept_bool",
            },
        )
    ],
)
def test_columns_from_concepts(link_role, duration_column_names, instant_column_names):
    """Test creation of column dictionary from concept tree."""
    link_role = LinkRole(**link_role)
    duration_resource = Resource.from_link_role(link_role, "duration", "test_path")
    instant_resource = Resource.from_link_role(link_role, "instant", "test_path")

    # Verify column names are correct
    duration_columns = {field.name: field for field in duration_resource.schema_.fields}
    instant_columns = {field.name: field for field in instant_resource.schema_.fields}

    assert duration_column_names == set(duration_columns.keys())
    assert instant_column_names == set(instant_columns.keys())

    # Verify data types
    assert duration_columns.get("duration_concept").type_ == "string"
    assert duration_columns.get("duration_concept_int").type_ == "integer"

    assert instant_columns.get("instant_concept").type_ == "string"
    assert instant_columns.get("child_concept").type_ == "year"
    assert instant_columns.get("concept_bool").type_ == "boolean"
