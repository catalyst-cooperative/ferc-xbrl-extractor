from collections import namedtuple
from pathlib import Path

import pytest

from ferc_xbrl_extractor.xbrl import ExtractOutput, extract

Dataset = namedtuple("Dataset", ["form", "year"])

DATASETS = [Dataset(form=f, year=y) for f in {1, 2, 6, 60, 714} for y in {2021, 2022}]


@pytest.fixture(scope="session")
def metadata_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("metadata")


@pytest.fixture(
    scope="session",
    params=DATASETS,
    ids=[f"form{ds.form}_{ds.year}" for ds in DATASETS],
)
def extracted(metadata_dir, data_dir, request) -> ExtractOutput:
    form, year = request.param
    return extract(
        taxonomy_source=data_dir / f"ferc{form}-xbrl-taxonomies.zip",
        form_number=form,
        db_uri="sqlite://:memory:",
        metadata_path=metadata_dir / "metadata.json",
        datapackage_path=metadata_dir / "datapackage.json",
        filings=[data_dir / f"ferc{form}-xbrl-{year}.zip"],
        workers=None,
        batch_size=8,
    )


def test_lost_facts_pct(extracted, request):
    table_defs_map, table_data, stats = extracted
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
        # Assert that this is < 0.97 so we remember to fix this test once we
        # fix the bug. We don't use xfail here because the parametrization is
        # at the *fixture* level, and only the lost facts tests should fail
        # for form 6.
        assert used_fact_ratio > total_threshold and used_fact_ratio <= 0.97
    else:
        total_threshold = 0.99
        per_filing_threshold = 0.95
        assert used_fact_ratio > total_threshold and used_fact_ratio <= 1

    for instance_stats in stats.values():
        instance_used_ratio = (
            len(instance_stats["used_facts"]) / instance_stats["total_facts"]
        )
        assert instance_used_ratio > per_filing_threshold and instance_used_ratio <= 1


def _get_relevant_table_defs(table_defs_map: dict):
    # Note: this just grabs table_defs from a random version of the taxonomy.
    # The taxonomy versions are close enough that this works for now, but this
    # could break tests in the future.
    return list(table_defs_map.values())[0]


def test_publication_time(extracted):
    table_defs_map, table_data, _stats = extracted
    table_defs = _get_relevant_table_defs(table_defs_map)

    for table_name, table in table_defs.items():
        assert (
            table_data[table_name]
            .reset_index(level="publication_time")
            .publication_time.notna()
            .all()
        )


def test_all_data_has_corresponding_id(extracted):
    table_defs_map, table_data, _stats = extracted
    table_defs = _get_relevant_table_defs(table_defs_map)

    [id_table_name] = [
        name
        for name in table_defs
        if name.startswith("ident") and name.endswith("_duration")
    ]
    id_table = table_data[id_table_name].reset_index()

    for table_name, table in table_defs.items():
        data_table = table_data[table_name]
        data_table = data_table.reset_index()
        merged = data_table.merge(
            id_table,
            how="left",
            on=["entity_id", "filing_name"],
            indicator=True,
        )
        assert (merged._merge != "left_only").all()


def test_null_values(extracted):
    table_defs_map, table_data, _stats = extracted
    table_defs = _get_relevant_table_defs(table_defs_map)

    for table_name, table in table_defs.items():
        dataframe = table_data[table_name]
        if dataframe.empty:
            continue
        # every row has at least one non-null value
        assert dataframe.notna().sum(axis=1).all()
