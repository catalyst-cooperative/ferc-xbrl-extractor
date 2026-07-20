"""Test XBRL extraction interface."""

import logging

import pandas as pd
import pytest

from ferc_xbrl_extractor.datapackage import Resource, clean_table_names, fuzzy_dedup
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
                "publication_time",
                "start_date",
                "end_date",
                "test_axis",
                "duration_concept",
                "duration_concept_int",
            },
            {
                "entity_id",
                "filing_name",
                "publication_time",
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


def test_fuzzy_dedup():
    fact_index = ["c_id", "name"]
    df = pd.DataFrame(
        [
            {"c_id": "a", "name": "cost", "value": 1.0},
            {"c_id": "a", "name": "cost", "value": 1.1},
            {"c_id": "a", "name": "job", "value": "accountant"},
            {"c_id": "b", "name": "cost", "value": 2.0},
            {"c_id": "b", "name": "cost", "value": 2.1},
            {"c_id": "b", "name": "cost", "value": 2.15},
            {"c_id": "b", "name": "job", "value": "Councilor"},
            {"c_id": "c", "name": "cost", "value": 3.0},
            {"c_id": "c", "name": "job", "value": "custodian"},
        ]
    ).set_index(fact_index)
    expected = pd.DataFrame(
        [
            {"c_id": "a", "name": "cost", "value": 1.1},
            {"c_id": "a", "name": "job", "value": "accountant"},
            {"c_id": "b", "name": "cost", "value": 2.15},
            {"c_id": "b", "name": "job", "value": "Councilor"},
            {"c_id": "c", "name": "cost", "value": 3.0},
            {"c_id": "c", "name": "job", "value": "custodian"},
        ]
    ).set_index(fact_index)

    pd.testing.assert_frame_equal(fuzzy_dedup(df), expected)


def test_fuzzy_dedup_failed_to_resolve():
    fact_index = ["c_id", "name"]
    df = pd.DataFrame(
        [
            {"c_id": "a", "name": "cost", "value": 1.1},
            {"c_id": "a", "name": "cost", "value": 1.2},
            {"c_id": "a", "name": "job", "value": "accountant"},
        ]
    ).set_index(fact_index)

    with pytest.raises(ValueError, match=r"Fact a:cost has values.*1.1.*1.2"):
        fuzzy_dedup(df)

    df = pd.DataFrame(
        [
            {"c_id": "a", "name": "cost", "value": 1.1},
            {"c_id": "a", "name": "job", "value": "accountant"},
            {"c_id": "a", "name": "job", "value": "pringle"},
        ]
    ).set_index(fact_index)

    with pytest.raises(
        ValueError, match=r"Fact a:job has values.*'accountant'.*'pringle'.*"
    ):
        fuzzy_dedup(df)


@pytest.mark.parametrize(
    "input_name,cleaned_name,is_bad",
    [
        ("001 - Schedule - Test Table Name", "test_table_name_001", False),
        ("002 - schedule - Lowercase Table Name", "lowercase_table_name_002", False),
        (
            "003 -    Schedule  - Weird Space Table Name",
            "weird_space_table_name_003",
            False,
        ),
        ("004 - Deprecated - Deprecated Table Name", None, False),
        ("005 - Bad - Bad Table Name", None, True),
    ],
)
def test_clean_table_names(input_name: str, cleaned_name: str | None, is_bad: bool):
    """Test clean_table_names method."""
    if is_bad:
        with pytest.raises(RuntimeError):
            clean_table_names(input_name)
    else:
        assert clean_table_names(input_name) == cleaned_name
