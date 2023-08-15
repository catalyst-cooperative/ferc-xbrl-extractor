import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from ferc_xbrl_extractor.cli import (  # TODO (daz) move this function out of CLI!
    TAXONOMY_MAP,
    get_instances,
)
from ferc_xbrl_extractor.xbrl import extract, get_fact_tables


@pytest.fixture(scope="session")
def metadata_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("metadata")


def get_available_test_datasets() -> list[dict[str, int]]:
    """Automatically generate test cases for all the files in our test data."""
    data_dir = Path(__file__).parent / "data"

    def extract_components(path: Path) -> dict[str, int]:
        match = re.match(r"ferc(\d+)-xbrl-(\d{4}).zip", path.name)
        return {"form": int(match.group(1)), "year": int(match.group(2))}

    return [extract_components(path) for path in data_dir.glob("*.zip")]


datasets = get_available_test_datasets()


@pytest.fixture(
    scope="session",
    params=datasets,
    ids=["form{form}_{year}".format(**ds) for ds in datasets],  # noqa: FS002
)
def extracted(test_dir, metadata_dir, request):
    form = request.param["form"]
    year = request.param["year"]

    tables = get_fact_tables(
        taxonomy_path=TAXONOMY_MAP[form],
        form_number=form,
        db_path="path",
        metadata_path=Path(metadata_dir) / "metadata.json",
    )
    instance_builders = get_instances(
        Path(test_dir) / "integration" / "data" / f"ferc{form}-xbrl-{year}.zip"
    )
    instances = [ib.parse() for ib in instance_builders]
    filings, metadata = extract(
        instances=instances,
        engine=create_engine("sqlite:///:memory:"),
        tables=tables,
        batch_size=max(1, len(instances) // 5),
        metadata_path=Path(metadata_dir) / "metadata.json",
    )
    return tables, instances, filings, metadata


@pytest.mark.xfail(reason="We don't have good lost facts handling yet.")
def test_lost_facts_pct(extracted):
    tables, instances, filings, metadata = extracted
    total_facts = sum(len(i.all_fact_ids) for i in instances)
    total_used_facts = sum(len(f_ids) for f_ids in metadata["fact_ids"].values())

    used_fact_ratio = total_used_facts / total_facts

    total_threshold = 0.99
    assert used_fact_ratio > total_threshold and used_fact_ratio <= 1

    filing_threshold = 0.95
    for instance in instances:
        instance_used_ratio = len(metadata["fact_ids"][instance.filing_name]) / len(
            instance.all_fact_ids
        )
        assert instance_used_ratio > filing_threshold and instance_used_ratio <= 1


def test_primary_key_uniqueness(extracted):
    tables, _instances, filings, _metadata = extracted

    for table_name, table in tables.items():
        if table.instant:
            date_cols = ["date"]
        else:
            date_cols = ["start_date", "end_date"]
        primary_key_cols = ["entity_id", "filing_name"] + date_cols + table.axes
        filing = filings[table_name].set_index(primary_key_cols)
        assert not filing.index.duplicated().any()


def test_null_values(extracted):
    tables, _instances, filings, _metadata = extracted

    for table_name, table in tables.items():
        if table.instant:
            date_cols = ["date"]
        else:
            date_cols = ["start_date", "end_date"]
        primary_key_cols = ["entity_id", "filing_name"] + date_cols + table.axes
        filing = filings[table_name].set_index(primary_key_cols)
        # every row has at least one non-null value
        assert filing.notna().sum(axis=1).all()
