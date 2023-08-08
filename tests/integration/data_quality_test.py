import os
from pathlib import Path

from ferc_xbrl_extractor.cli import (
    get_instances,
    TAXONOMY_MAP,
)  # TODO (daz) move this function out of CLI!
from ferc_xbrl_extractor.xbrl import get_fact_tables, extract
from sqlalchemy import create_engine


def test_row_count(test_dir, tmp_path):
    instances = get_instances(
        Path(test_dir) / "integration" / "data" / "ferc1-xbrl-2021.zip"
    )

    tables = get_fact_tables(
        taxonomy_path=TAXONOMY_MAP[1],
        form_number=1,
        db_path="path",
        metadata_path=Path(tmp_path) / "metadata.json",
    )

    # TODO (daz): pass in the taxonomy object here instead of just the path.
    filings = extract(
        instances=instances[:10],
        engine=create_engine("sqlite:///:memory:"),
        taxonomy=TAXONOMY_MAP[1],
        form_number=1,
        batch_size=5,
        metadata_path=Path(tmp_path) / "metadata.json",
    )

    for name, filing in filings.items():
        breakpoint()
        assert filing.empty
