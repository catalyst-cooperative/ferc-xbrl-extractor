import re
from collections import namedtuple
from pathlib import Path

import pytest

from ferc_xbrl_extractor.cli import (  # TODO (daz) move this function out of CLI!
    TAXONOMY_MAP,
    get_instances,
)
from ferc_xbrl_extractor.xbrl import extract, get_fact_tables

Dataset = namedtuple("Dataset", ["form", "year", "path"])


ExtractOutput = namedtuple("ExtractOutput", ["tables", "instances", "filings", "stats"])


@pytest.fixture(scope="session")
def metadata_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("metadata")


@pytest.fixture(scope="session")
def data_dir(request) -> Path:
    return request.config.getoption("--integration-data-dir")


@pytest.fixture(scope="session")
def test_datasets(data_dir) -> list[Dataset]:
    """Get available test datasets"""

    def extract_components(path: Path) -> dict[str, int]:
        match = re.match(r"ferc(\d+)-xbrl-(\d{4}).zip", path.name)
        return Dataset(form=int(match.group(1)), year=int(match.group(2)), path=path)

    return [extract_components(path) for path in data_dir.glob("ferc*-xbrl-*.zip")]


@pytest.fixture(scope="session")
def extracted(metadata_dir, test_datasets) -> dict[Dataset, ExtractOutput]:
    def extract_dataset(dataset: Dataset) -> ExtractOutput:
        tables = get_fact_tables(
            taxonomy_path=TAXONOMY_MAP[dataset.form],
            form_number=dataset.form,
            db_path="path",
            metadata_path=Path(metadata_dir) / "metadata.json",
        )
        instance_builders = get_instances(dataset.path)
        instances = [ib.parse() for ib in instance_builders]
        filings, stats = extract(
            instances=instances,
            tables=tables,
            batch_size=max(1, len(instances) // 5),
        )
        return ExtractOutput(
            tables=tables, instances=instances, filings=filings, stats=stats
        )

    return {dataset: extract_dataset(dataset) for dataset in test_datasets}


def _test_lost_facts_pct(extracted, dataset):
    tables, instances, filings, stats = extracted[dataset]
    total_facts = sum(len(i.all_fact_ids) for i in instances)
    total_used_facts = sum(len(f_ids) for f_ids in stats["fact_ids"].values())

    used_fact_ratio = total_used_facts / total_facts

    total_threshold = 0.99
    assert used_fact_ratio > total_threshold and used_fact_ratio <= 1

    filing_threshold = 0.95
    for instance in instances:
        instance_used_ratio = len(stats["fact_ids"][instance.filing_name]) / len(
            instance.all_fact_ids
        )
        assert instance_used_ratio > filing_threshold and instance_used_ratio <= 1


@pytest.mark.xfail(reason="We don't have good lost facts handling yet.")
def test_lost_facts_pct(extracted, test_datasets):
    for dataset in test_datasets:
        _test_lost_facts_pct(extracted, dataset)


def _test_primary_key_uniqueness(extracted, dataset):
    tables, _instances, filings, _stats = extracted[dataset]

    for table_name, table in tables.items():
        if table.instant:
            date_cols = ["date"]
        else:
            date_cols = ["start_date", "end_date"]
        primary_key_cols = ["entity_id", "filing_name"] + date_cols + table.axes
        filing = filings[table_name].set_index(primary_key_cols)
        assert not filing.index.duplicated().any()


def test_primary_key_uniqueness(extracted, test_datasets):
    for dataset in test_datasets:
        _test_primary_key_uniqueness(extracted, dataset)


def _test_null_values(extracted, dataset):
    tables, _instances, filings, _stats = extracted[dataset]

    for table_name, table in tables.items():
        if table.instant:
            date_cols = ["date"]
        else:
            date_cols = ["start_date", "end_date"]
        primary_key_cols = ["entity_id", "filing_name"] + date_cols + table.axes
        filing = filings[table_name].set_index(primary_key_cols)
        # every row has at least one non-null value
        assert filing.notna().sum(axis=1).all()


def test_null_values(extracted, test_datasets):
    for dataset in test_datasets:
        _test_null_values(extracted, dataset)
