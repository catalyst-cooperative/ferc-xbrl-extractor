"""Test the FERC XBRL extractor CLI helpers."""

import json

import pytest

from ferc_xbrl_extractor.cli import convert_and_validate_datapackage_sqlite_to_parquet


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
