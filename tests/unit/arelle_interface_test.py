"""Test the internal Arelle interface helpers."""

import pytest

import ferc_xbrl_extractor.arelle_interface as arelle_interface


def test_taxonomy_view_retries_then_raises_after_max_retries(mocker):
    """_taxonomy_view() retries with exponential backoff, then re-raises.

    Regression coverage for the retry loop, which handles Arelle's shared
    taxonomy cache raising FileExistsError under concurrent access. See
    test_concurrent_taxonomy_load in tests/integration/arelle_interface_test.py
    for a real (but not reliably triggered) end-to-end exercise of this same
    path -- this test forces the failure deterministically instead.
    """
    mocker.patch.object(
        arelle_interface.Cntlr, "Cntlr", return_value=mocker.MagicMock()
    )
    mocker.patch.object(
        arelle_interface.ModelManager, "initialize", return_value=mocker.MagicMock()
    )
    mock_sleep = mocker.patch.object(arelle_interface.time, "sleep")
    mock_load = mocker.patch.object(
        arelle_interface.ModelXbrl, "load", side_effect=FileExistsError
    )

    with pytest.raises(FileExistsError):
        arelle_interface._taxonomy_view("fake_source", max_retries=3)

    assert mock_load.call_count == 3
    mock_sleep.assert_has_calls([mocker.call(2), mocker.call(4)])
