from ferc_xbrl_extractor.datapackage import FactTable, Field, Schema
from ferc_xbrl_extractor.instance import InstanceBuilder
from ferc_xbrl_extractor.xbrl import table_data_from_instances


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
