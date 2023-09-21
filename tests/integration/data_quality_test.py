from collections import namedtuple
from pathlib import Path

import pytest

from ferc_xbrl_extractor.xbrl import ExtractOutput, extract

Dataset = namedtuple("Dataset", ["form", "year"])

DATASETS = [Dataset(form=f, year=y) for f in {1, 2, 6, 60, 714} for y in {2021, 2022}]


@pytest.fixture(scope="session")
def metadata_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("metadata")


@pytest.fixture(scope="session")
def data_dir(request) -> Path:
    return request.config.getoption("--integration-data-dir")


@pytest.fixture(
    scope="session",
    params=DATASETS,
    ids=[f"form{ds.form}_{ds.year}" for ds in DATASETS],
)
def extracted(metadata_dir, data_dir, request) -> ExtractOutput:
    form, year = request.param
    return extract(
        taxonomy_source=data_dir / f"ferc{form}-2022-taxonomy.zip",
        form_number=form,
        db_uri="sqlite://:memory:",
        entry_point=f"taxonomy/form{form}/2022-01-01/form/form{form}/form-{form}_2022-01-01.xsd",
        metadata_path=metadata_dir / "metadata.json",
        datapackage_path=metadata_dir / "datapackage.json",
        instance_path=data_dir / f"ferc{form}-xbrl-{year}.zip",
        workers=None,
        batch_size=8,
    )


def test_lost_facts_pct(extracted, request):
    table_defs, table_data, stats = extracted
    total_facts = sum(
        instance_stats["total_facts"] for instance_stats in stats.values()
    )
    total_used_facts = sum(
        len(instance_stats["used_facts"]) for instance_stats in stats.values()
    )
    used_fact_ratio = total_used_facts / total_facts

    if "form6_" in request.node.name:
        # We have unallocated data for Form 6 for some reason.
        total_threshold = 0.9
        per_filing_threshold = 0.8
        # Assert that this is < 0.95 so we remember to fix this test once we
        # fix the bug. We don't use xfail here because the parametrization is
        # at the *fixture* level, and only the lost facts tests should fail
        # for form 6.
        assert used_fact_ratio > total_threshold and used_fact_ratio <= 0.95
    else:
        total_threshold = 0.99
        per_filing_threshold = 0.95
        assert used_fact_ratio > total_threshold and used_fact_ratio <= 1

    for instance_stats in stats.values():
        instance_used_ratio = (
            len(instance_stats["used_facts"]) / instance_stats["total_facts"]
        )
        assert instance_used_ratio > per_filing_threshold and instance_used_ratio <= 1


def test_deduplication(extracted):
    table_defs, table_data, _stats = extracted

    for table_name, table in table_defs.items():
        date_cols = ["date"] if table.instant else ["start_date", "end_date"]
        # we want to make sure that any fact only comes from one filing, so we
        # don't want to include filing_name in the unique_cols
        if (df := table_data[table_name]).empty:
            continue
        unique_cols = ["entity_id"] + date_cols + table.axes
        assert not df.reset_index().duplicated(unique_cols).any()


def test_null_values(extracted):
    table_defs, table_data, _stats = extracted

    for table_name, table in table_defs.items():
        dataframe = table_data[table_name]
        if dataframe.empty:
            continue
        # every row has at least one non-null value
        assert dataframe.notna().sum(axis=1).all()
