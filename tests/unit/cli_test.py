"""Test the FERC XBRL extractor CLI helpers."""

import json

import duckdb
import pyarrow.parquet as pq
import pytest

from ferc_xbrl_extractor import PARQUET_COMPRESSION
from ferc_xbrl_extractor.cli import (
    convert_and_validate_datapackage_sqlite_to_parquet,
    convert_duckdb_into_parquet,
)


def test_convert_duckdb_into_parquet_uses_configured_compression(tmp_path):
    """Parquet outputs are compressed using the package's configured codec.

    Regression test: we want smaller, faster-to-read Parquet outputs than
    DuckDB's default Snappy compression, without paying for a high ZSTD level,
    and we want every Parquet call site to share one source of truth for the
    compression settings.
    """
    duckdb_path = tmp_path / "test.duckdb"
    parquet_dir = tmp_path / "parquet"

    with duckdb.connect(duckdb_path) as con:
        con.execute("CREATE TABLE test_table AS SELECT * FROM range(1000) AS t(x)")

    convert_duckdb_into_parquet(duckdb_path=duckdb_path, parquet_dir=parquet_dir)

    parquet_file = pq.ParquetFile(parquet_dir / "test_table.parquet")
    column_meta = parquet_file.metadata.row_group(0).column(0)

    assert column_meta.compression == PARQUET_COMPRESSION.upper()


def test_convert_and_validate_datapackage_sqlite_to_parquet_rejects_invalid(
    tmp_path, mocker
):
    """Raises a clear error if the rewritten datapackage fails validation.

    Forces the failure by mocking frictionless's validator, since constructing a
    real datapackage descriptor that's invalid in just the right way isn't worth
    the trouble -- this is purely testing that the check-and-raise wiring works.
    """
    datapackage = {
        "resources": [
            {
                "name": "test_table",
                "path": "test_table",
                "dialect": {"table": "test_table"},
            }
        ]
    }
    datapackage_path = tmp_path / "datapackage.json"
    datapackage_path.write_text(json.dumps(datapackage))

    mock_report = mocker.Mock(valid=False, errors=["some validation error"])
    mocker.patch(
        "ferc_xbrl_extractor.cli.Package.validate_descriptor",
        return_value=mock_report,
    )

    with pytest.raises(RuntimeError, match="Generated datapackage is invalid"):
        convert_and_validate_datapackage_sqlite_to_parquet(datapackage_path)
