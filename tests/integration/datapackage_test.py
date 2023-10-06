"""Test datapackage descriptor from taxonomy."""
import datetime
import io
from pathlib import Path

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


def test_datapackage_generation(test_dir):
    """Test that datapackage descriptor is valid."""
    taxonomy = Taxonomy.from_source(
        test_dir / "integration/data/ferc1-2022-taxonomy.zip",
        entry_point=Path("taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd"),
    )
    datapackage = Datapackage.from_taxonomy(taxonomy, "sqlite:///test_db.sqlite")

    filtered_tables = datapackage.get_fact_tables(
        filter_tables={"identification_001_duration"}
    )
    assert set(filtered_tables.keys()) == {"identification_001_duration"}

    all_tables = datapackage.get_fact_tables()

    # 366 was just the value we had - this assertion is more of a regression
    # test than a normative statement
    assert len(all_tables) == 366

    assert Package(descriptor=datapackage.dict(by_alias=True)).metadata_valid


def _create_schema(instant=True, axes=None):
    if not axes:
        axes = []

    axes = [Field(name=axis, title="", description="") for axis in axes]

    default_cols = INSTANT_COLUMNS if instant else DURATION_COLUMNS

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
            Field(name="null_col", title="", description=""),
        ],
        primary_key=primary_key,
    )


@pytest.mark.parametrize(
    "table_schema,period,df",
    [
        (
            _create_schema(instant=False),
            "duration",
            pd.read_csv(
                io.StringIO(
                    "c_id,entity_id,filing_name,publication_time,start_date,end_date,column_one,column_two,null_col\n"
                    'cid_1,EID1,filing,2023-01-01T00:00:01,2021-01-01,2021-12-31,"value 1","value 2",\n'
                    'cid_4,EID1,filing,2023-01-01T00:00:01,2020-01-01,2020-12-31,"value 3","value 4",\n'
                ),
                parse_dates=["publication_time"],
            ),
        ),
        (
            _create_schema(instant=False, axes=["dimension_one_axis"]),
            "duration",
            pd.read_csv(
                io.StringIO(
                    "c_id,entity_id,filing_name,publication_time,start_date,end_date,dimension_one_axis,column_one,column_two,null_col\n"
                    'cid_1,EID1,filing,2023-01-01T00:00:01,2021-01-01,2021-12-31,total,"value 1","value 2",\n'
                    'cid_4,EID1,filing,2023-01-01T00:00:01,2020-01-01,2020-12-31,total,"value 3","value 4",\n'
                    'cid_5,EID1,filing,2023-01-01T00:00:01,2020-01-01,2020-12-31,"Dim 1 Value","value 9","value 10",\n'
                ),
                parse_dates=["publication_time"],
            ),
        ),
        (
            _create_schema(axes=["dimension_one_axis", "dimension_two_axis"]),
            "instant",
            pd.read_csv(
                io.StringIO(
                    "c_id,entity_id,filing_name,publication_time,date,dimension_one_axis,dimension_two_axis,column_one,column_two,null_col\n"
                    'cid_2,EID1,filing,2023-01-01T00:00:01,2021-12-31,total,total,"value 5","value 6",\n'
                    'cid_3,EID1,filing,2023-01-01T00:00:01,2021-12-31,"Dim 1 Value","ferc:Dimension2Value","value 7","value 8",\n'
                ),
                parse_dates=["publication_time"],
            ),
        ),
    ],
)
def test_construct_dataframe(table_schema, period, df, in_memory_filing):
    """Test dataframe construction."""
    instance_builder = InstanceBuilder(
        in_memory_filing,
        "filing",
        publication_time=datetime.datetime(2023, 1, 1, 0, 0, 1),
    )
    instance = instance_builder.parse()

    fact_table = FactTable(table_schema, period)

    constructed_df = fact_table.construct_dataframe(instance).reset_index()
    constructed_df = constructed_df.astype({"publication_time": "datetime64[s]"})
    expected_df = (
        df.set_index(table_schema.primary_key)
        .drop("c_id", axis="columns")
        .reset_index()
    )
    expected_df = expected_df.astype({"publication_time": "datetime64[s]"})
    pd.testing.assert_frame_equal(expected_df, constructed_df)
