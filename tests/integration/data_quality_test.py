import os
from pathlib import Path

from ferc_xbrl_extractor.cli import (
    get_instances,
    TAXONOMY_MAP,
)  # TODO (daz) move this function out of CLI!
from ferc_xbrl_extractor.xbrl import get_fact_tables, extract
from sqlalchemy import create_engine
import pytest


@pytest.fixture(scope="session")
def metadata_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("metadata")


@pytest.fixture(scope="session")
def tables(metadata_dir):
    return get_fact_tables(
        taxonomy_path=TAXONOMY_MAP[1],
        form_number=1,
        db_path="path",
        metadata_path=Path(metadata_dir) / "metadata.json",
    )


@pytest.fixture(scope="session", params=["ferc1-xbrl-2021.zip"])
def extracted(test_dir, metadata_dir, request):
    instance_builders = get_instances(
        Path(test_dir) / "integration" / "data" / "ferc1-xbrl-2021.zip"
    )
    num_instances = 10  # len(instance_builders)
    # TODO (daz): pass in the taxonomy object here instead of just the path.
    # can I get rid of both metadata_path and taxonomy?
    instances = [ib.parse() for ib in instance_builders][:num_instances]
    filings, metadata = extract(
        instances=instances,
        engine=create_engine("sqlite:///:memory:"),
        taxonomy=TAXONOMY_MAP[1],
        form_number=1,
        batch_size=1 + num_instances // 5,
        metadata_path=Path(metadata_dir) / "metadata.json",
    )
    return instances, filings, metadata


def test_lost_facts_pct(extracted):
    instances, filings, metadata = extracted
    total_facts = sum(len(i.all_fact_ids) for i in instances)
    total_used_facts = sum(len(f_ids) for f_ids in metadata["fact_ids"].values())

    used_fact_ratio = total_used_facts / total_facts

    assert used_fact_ratio > 0.99 and used_fact_ratio <= 1

    for instance in instances:
        instance_used_ratio = len(
            metadata["fact_ids"][instance.name].used_fact_ids
        ) / len(instance.all_fact_ids)
        assert instance_used_ratio > 0.95 and instance_used_ratio <= 1


def test_primary_key_uniqueness(tables, extracted):
    _instances, filings, _metadata = extracted

    for table_name, table in tables.items():
        if table.instant:
            date_cols = ["date"]
        else:
            date_cols = ["start_date", "end_date"]
        primary_key_cols = ["entity_id", "filing_name"] + date_cols + table.axes
        filing = filings[table_name].set_index(primary_key_cols)
        assert not filing.index.duplicated().any()


def test_null_values(tables, extracted):
    _instances, filings, _metadata = extracted

    for table_name, table in tables.items():
        if table.instant:
            date_cols = ["date"]
        else:
            date_cols = ["start_date", "end_date"]
        primary_key_cols = ["entity_id", "filing_name"] + date_cols + table.axes
        filing = filings[table_name].set_index(primary_key_cols)
        # every row has at least one non-null value
        assert filing.notna().sum(axis=1).all()
