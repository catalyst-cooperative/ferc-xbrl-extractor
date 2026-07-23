import pandas as pd
from lxml.etree import XMLSyntaxError  # nosec: B410

from ferc_xbrl_extractor.xbrl import process_batch, process_instance


def test_process_instance(mocker):
    """process_instance() builds a dict of dataframes from the requested tables.

    process_batch() is the only other caller, and only exercises this indirectly
    via a ProcessPoolExecutor worker subprocess (see data_quality_test.py), whose
    execution coverage.py doesn't capture -- so this needs its own direct test.
    Table construction itself is FactTable.construct_dataframe()'s job (tested
    separately), so this just checks the looping/dict-building contract.
    """
    instance = mocker.Mock(filing_name="test_filing")
    fake_df = pd.DataFrame({"value": [1, 2, 3]})
    table_def = mocker.Mock()
    table_def.construct_dataframe.return_value = fake_df

    result = process_instance(instance, table_defs={"my_table": table_def})

    assert result == {"my_table": fake_df}
    table_def.construct_dataframe.assert_called_once_with(instance)


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

    # MockInstanceBuilder and the list[str] table_defs are deliberately loose
    # stand-ins: process_instance is mocked out below, so neither argument's real
    # structure is ever exercised, and building real InstanceBuilder/FactTable
    # fixtures here wouldn't test anything more.
    results = process_batch(instances, table_defs)  # pyrefly: ignore[bad-argument-type]

    for table in table_defs:
        pd.testing.assert_frame_equal(
            expected_dfs[table],
            results["dfs"][table].reset_index(drop=True),
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
