"""Test XBRL extraction interface."""
import logging

import pytest

from xbrl_extract.taxonomy import Concept
from xbrl_extract.xbrl import get_columns_from_concept_tree

logger = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "concept,column_names",
    [
        (
            {
                "name": "test_concept",
                "documentation": "Test concept.",
                "type": {
                    "name": "type",
                    "base": "string",
                },
                "period_type": "duration",
                "child_concepts": [
                    {
                        "name": "TestAxis",
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
                        "documentation": "Test a generic duration column.",
                        "type": {"name": "type", "base": "string"},
                        "period_type": "duration",
                        "child_concepts": [],
                    },
                    {
                        "name": "DurationConceptInt",
                        "documentation": "Test a duration column with int type.",
                        "type": {"name": "type", "base": "integer"},
                        "period_type": "duration",
                        "child_concepts": [],
                    },
                    {
                        "name": "InstantConcept",
                        "documentation": "Test a generic instant column.",
                        "type": {"name": "type", "base": "string"},
                        "period_type": "instant",
                        "child_concepts": [],
                    },
                    {
                        "name": "ConceptContainer",
                        "documentation": "Test a concept with child concepts.",
                        "type": {"name": "type", "base": "string"},
                        "period_type": "instant",
                        "child_concepts": [
                            {
                                "name": "ChildConcept",
                                "documentation": "Test child concept.",
                                "type": {"name": "type", "base": "gyear"},
                                "period_type": "instant",
                                "child_concepts": [],
                            },
                        ],
                    },
                    {
                        "name": "ConceptBool",
                        "documentation": "Test a column with bool type.",
                        "type": {"name": "type", "base": "boolean"},
                        "period_type": "instant",
                        "child_concepts": [],
                    },
                ],
            },
            {
                "DurationConcept",
                "DurationConceptInt",
                "InstantConcept",
                "ChildConcept",
                "ConceptBool",
            },
        )
    ],
)
def test_columns_from_concepts(concept, column_names):
    """Test creation of column dictionary from concept tree."""
    concept = Concept(**concept)
    columns = get_columns_from_concept_tree(concept)
    duration_columns = columns["duration"]
    instant_columns = columns["instant"]
    print(instant_columns)

    # Verify column names are correct
    column_names_found = set(duration_columns.keys())
    column_names_found.update(instant_columns.keys())
    assert column_names == column_names_found

    # Verify data types
    assert duration_columns.get("DurationConcept").base == "string"
    assert duration_columns.get("DurationConceptInt").base == "integer"

    assert instant_columns.get("InstantConcept").base == "string"
    assert instant_columns.get("ChildConcept").base == "gyear"
    assert instant_columns.get("ConceptBool").base == "boolean"
