"""Test datapackage descriptor from taxonomy."""
import pandas as pd
import pytest
from frictionless import Package

from ferc_xbrl_extractor.datapackage import (
    DURATION_COLUMNS,
    INSTANT_COLUMNS,
    Datapackage,
    FactTable,
    Field,
    Schema,
)
from ferc_xbrl_extractor.instance import InstanceBuilder
from ferc_xbrl_extractor.taxonomy import Taxonomy


@pytest.mark.parametrize(
    "taxonomy_url",
    [
        "https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd"
    ],
)
def test_datapackage_generation(taxonomy_url):
    """Test that datapackage descriptor is valid."""
    taxonomy = Taxonomy.from_path(taxonomy_url)
    datapackage = Datapackage.from_taxonomy(taxonomy, "sqlite:///test_db.sqlite")
    assert Package(descriptor=datapackage.dict(by_alias=True)).metadata_valid


def _create_schema(instant=True, axes=None):
    if not axes:
        axes = []

    axes = [Field(name=axis, title="", description="") for axis in axes]

    if instant:
        default_cols = INSTANT_COLUMNS
    else:
        default_cols = DURATION_COLUMNS

    primary_key = [
        *[col.name for col in default_cols],
        *[col.name for col in axes],
    ]
    return Schema(
        fields=[
            *default_cols,
            *axes,
            Field(name="column_one", title="", description=""),
            Field(name="column_two", title="", description=""),
        ],
        primary_key=primary_key,
    )


@pytest.mark.parametrize(
    "table_schema,period,df",
    [
        (
            _create_schema(instant=False),
            "duration",
            pd.DataFrame(
                {
                    "cid_1": {
                        "entity_id": "EID1",
                        "filing_name": "filing",
                        "start_date": "2021-01-01",
                        "end_date": "2021-12-31",
                        "column_one": "value 1",
                        "column_two": "value 2",
                    },
                    "cid_4": {
                        "entity_id": "EID1",
                        "filing_name": "filing",
                        "start_date": "2020-01-01",
                        "end_date": "2020-12-31",
                        "column_one": "value 3",
                        "column_two": "value 4",
                    },
                }
            ).T,
        ),
        (
            _create_schema(instant=False, axes=["dimension_one_axis"]),
            "duration",
            pd.DataFrame(
                {
                    "cid_1": {
                        "entity_id": "EID1",
                        "filing_name": "filing",
                        "start_date": "2021-01-01",
                        "end_date": "2021-12-31",
                        "dimension_one_axis": "Total",
                        "column_one": "value 1",
                        "column_two": "value 2",
                    },
                    "cid_4": {
                        "entity_id": "EID1",
                        "filing_name": "filing",
                        "start_date": "2020-01-01",
                        "end_date": "2020-12-31",
                        "dimension_one_axis": "Total",
                        "column_one": "value 3",
                        "column_two": "value 4",
                    },
                    "cid_5": {
                        "entity_id": "EID1",
                        "filing_name": "filing",
                        "start_date": "2020-01-01",
                        "end_date": "2020-12-31",
                        "dimension_one_axis": "Dim 1 Value",
                        "column_one": "value 9",
                        "column_two": "value 10",
                    },
                }
            ).T,
        ),
        (
            _create_schema(axes=["dimension_one_axis", "dimension_two_axis"]),
            "instant",
            pd.DataFrame(
                {
                    "cid_2": {
                        "entity_id": "EID1",
                        "filing_name": "filing",
                        "date": "2021-12-31",
                        "dimension_one_axis": "Total",
                        "dimension_two_axis": "Total",
                        "column_one": "value 5",
                        "column_two": "value 6",
                    },
                    "cid_3": {
                        "entity_id": "EID1",
                        "filing_name": "filing",
                        "date": "2021-12-31",
                        "dimension_one_axis": "Dim 1 Value",
                        "dimension_two_axis": "ferc:Dimension2Value",
                        "column_one": "value 7",
                        "column_two": "value 8",
                    },
                }
            ).T,
        ),
    ],
)
def test_construct_dataframe(table_schema, period, df, in_memory_filing):
    """Test dataframe construction."""
    instance_builder = InstanceBuilder(in_memory_filing, "filing")
    instance = instance_builder.parse()

    fact_table = FactTable(table_schema, period)

    constructed_df = fact_table.construct_dataframe(instance)
    pd.testing.assert_frame_equal(df, constructed_df)
