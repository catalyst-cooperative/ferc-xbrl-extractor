"""Integration tests for ferc_xbrl_extractor.xbrl."""

import pytest

from ferc_xbrl_extractor.xbrl import get_fact_tables


def test_get_fact_tables_rejects_invalid_datapackage(data_dir, tmp_path, mocker):
    """get_fact_tables() raises a clear error if the generated datapackage is invalid.

    Forces the failure by mocking frictionless's validator, since we don't have a
    real taxonomy on hand that happens to produce an invalid datapackage -- this
    is purely testing that the check-and-raise wiring works.
    """
    mock_report = mocker.Mock(valid=False, errors=["some validation error"])
    mocker.patch(
        "ferc_xbrl_extractor.xbrl.Package.validate_descriptor",
        return_value=mock_report,
    )

    with pytest.raises(RuntimeError, match="Generated datapackage is invalid"):
        get_fact_tables(
            taxonomy_source=data_dir / "ferc1-xbrl-taxonomies.zip",
            form_number=1,
            db_uri="sqlite:///test.sqlite",
            datapackage_path=tmp_path / "datapackage.json",
        )
