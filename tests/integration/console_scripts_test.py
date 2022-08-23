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
def test_pudl_scripts(script_runner, ep):
    """Run each deployed console script with --help for testing.

    The script_runner fixture is provided by the pytest-console-scripts plugin.
    """
    ret = script_runner.run(ep, "--help", print_result=False)
    assert ret.success  # nosec: B101
