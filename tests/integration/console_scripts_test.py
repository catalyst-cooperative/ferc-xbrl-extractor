"""Test the PUDL console scripts from within PyTest."""

import pkg_resources
import pytest

# Obtain a list of all deployed entry point scripts to test:
ENTRY_POINTS = [
    ep.name
    for ep in pkg_resources.iter_entry_points("console_scripts")
    if ep.module_name.startswith("xbrl_extract")
]


@pytest.mark.parametrize("ep", ENTRY_POINTS)
@pytest.mark.script_launch_mode("inprocess")
def test_extractor_scripts(script_runner, ep):
    """Run each deployed console script with --help for testing.

    The script_runner fixture is provided by the pytest-console-scripts plugin.
    """
    ret = script_runner.run(ep, "--help", print_result=False)
    assert ret.success  # nosec: B101


@pytest.mark.script_launch_mode("inprocess")
def test_extract_example_filings(script_runner):
    """Test the XBRL extraction on the example filings.

    Run the example CLI command from the readme, that will perform an extraction
    with the example filings and taxonomy in the ``examples/`` directory, and verify
    that it returns successfully.
    """
    ret = script_runner.run(
        "xbrl_extract",
        "examples/ferc1-2021-sample.zip",
        "./ferc1-2021-sample.sqlite",
        "--taxonomy",
        "examples/taxonomy.zip",
        "--archive-path",
        "taxonomy/form1/2021-01-01/form/form1/form-1_2021-01-01.xsd",
        "--metadata-path",
        "metadata.json",
        "--save-datapackage",
        "datapackage.json",
    )

    assert ret.success
