import pandas as pd
from lxml.etree import XMLSyntaxError  # nosec: B410

from ferc_xbrl_extractor.datapackage import FactTable, Field, Schema
from ferc_xbrl_extractor.instance import InstanceBuilder
from ferc_xbrl_extractor.xbrl import process_batch, table_data_from_instances


def test_process_batch(mocker):
    class MockInstanceBuilder:
        def __init__(
            self, filing_name, used_fact_ids, total_facts, raise_exception=False
        ):
            self.raise_exception = raise_exception
            self.filing_name = filing_name
            self.name = filing_name
            self.used_fact_ids = used_fact_ids
            self.total_facts = total_facts

        def parse(self):
            if self.raise_exception:
                raise XMLSyntaxError("message", 1, 0, 0)
            return self

    test_data = {
        "instance_1": {
            "raise_exception": False,
            "used_fact_ids": 3,
            "total_facts": 4,
        },
        "instance_2": {"raise_exception": False, "used_fact_ids": 5, "total_facts": 8},
        "instance_3": {"raise_exception": False, "used_fact_ids": 8, "total_facts": 9},
        "instance_4": {"raise_exception": True, "used_fact_ids": 12, "total_facts": 13},
    }

    instances = [
        MockInstanceBuilder(
            key, vals["used_fact_ids"], vals["total_facts"], vals["raise_exception"]
        )
        for key, vals in test_data.items()
    ]
    table_defs = ["table_1", "table_2", "table_3"]

    mocker.patch(
        "ferc_xbrl_extractor.xbrl.process_instance",
        side_effect=lambda instance, tables: {
            table: pd.DataFrame({table: [instance.filing_name]}) for table in tables
        },
    )

    expected_dfs = {
        table: pd.DataFrame(
            {
                table: [
                    filing_name
                    for filing_name, vals in test_data.items()
                    if not vals["raise_exception"]
                ]
            }
        )
        for table in table_defs
    }

    results = process_batch(instances, table_defs)

    for table in table_defs:
        pd.testing.assert_frame_equal(
            expected_dfs[table], results["dfs"][table].reset_index(drop=True)
        )

    metadata = results["metadata"]
    for filing_name, expected_metadata in test_data.items():
        if not expected_metadata["raise_exception"]:
            assert (
                metadata[filing_name]["used_facts"]
                == expected_metadata["used_fact_ids"]
            )
            assert (
                metadata[filing_name]["total_facts"] == expected_metadata["total_facts"]
            )
        else:
            assert filing_name not in metadata


def test_table_data_dedupes(multi_filings):
    instance_builders = [
        InstanceBuilder(f, name=f"instance_{i}") for i, f in enumerate(multi_filings)
    ]

    duration_schema = Schema(
        fields=[
            Field(name="column_one", title="ColumnOne", description="c1"),
            Field(name="column_two", title="ColumnTwo", description="c2"),
        ],
        primary_key=["entity_id", "filing_name", "start_date", "end_date"],
    )

    instant_schema = Schema(
        fields=[
            Field(name="column_one", title="ColumnOne", description="c1"),
            Field(name="column_two", title="ColumnTwo", description="c2"),
            Field(name="column_three", title="ColumnThree", description="c3"),
            Field(name="column_four", title="ColumnFour", description="c4"),
        ],
        primary_key=["entity_id", "filing_name", "date"],
    )
    taxonomy = {
        "instant": FactTable(schema=instant_schema, period_type="instant"),
        "duration": FactTable(schema=duration_schema, period_type="duration"),
    }
    table_data, _stats = table_data_from_instances(
        instance_builders=instance_builders,
        table_defs=taxonomy,
    )

    # there are two different facts sharing the same context dimensions, but not the same context ID
    # is it our business to detect this in the extraction step? probably.
    assert len(table_data["duration"]) == 2
    assert (
        table_data["duration"]["column_one"].sort_values() == ["value 1.1", "value 3.1"]
    ).all()
    assert (
        table_data["duration"]["column_two"].sort_values() == ["value 2.1", "value 4.1"]
    ).all()

    assert len(table_data["instant"]) == 1
    assert (table_data["instant"]["column_one"] == "value 5.1").all()
    assert (table_data["instant"]["column_two"] == "value 6.1").all()
    assert (table_data["instant"]["column_three"] == "value 11.1").all()
    assert (table_data["instant"]["column_four"] == "value 12").all()
