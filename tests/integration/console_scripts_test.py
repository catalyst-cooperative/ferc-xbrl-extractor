"""Test the PUDL console scripts from within PyTest."""

from importlib.metadata import entry_points

import duckdb
import pandas as pd
import pytest

# Obtain a list of all deployed entry point scripts to test:
ENTRY_POINTS = [
    ep.name
    for ep in entry_points(group="console_scripts")
    if ep.name.startswith("xbrl_extract")
]


@pytest.mark.parametrize("ep", ENTRY_POINTS)
@pytest.mark.script_launch_mode("inprocess")
def test_extractor_scripts(script_runner, ep):
    """Run each deployed console script with --help for testing.

    The script_runner fixture is provided by the pytest-console-scripts plugin.
    """
    ret = script_runner.run([ep, "--help"], print_result=False)
    assert ret.success  # nosec: B101


def _get_tables(conn) -> set[str]:
    """Return set of all tables in duckdb."""
    tables = conn.execute("SELECT table_name FROM information_schema.tables").fetchall()
    return {table_name for (table_name,) in tables}


def _find_empty_tables(db_conn, tables: set[str]) -> list[str]:
    """Loop through tables and identify any that are empty."""
    empty_tables = []
    for table_name in tables:
        query = f"SELECT COUNT(*) FROM '{table_name}';"  # noqa: S608
        if db_conn.execute(query).fetchone()[0] == 0:
            empty_tables.append(table_name)
    return empty_tables


def _get_sqlite_df(db_conn, table: str) -> pd.DataFrame:
    df = db_conn.table(table).df()
    return df.astype(
        dict.fromkeys(df.select_dtypes(include=["datetime"]).columns, "datetime64[ms]")
    )


@pytest.mark.script_launch_mode("inprocess")
def test_extract_example_filings(script_runner, tmp_path, test_dir):
    """Test the XBRL extraction on the example filings.

    Run the example CLI command from the readme, that will perform an extraction
    with the example filings and taxonomy in the ``examples/`` directory, and verify
    that it returns successfully.
    """
    sqlite_path = tmp_path / "ferc1-2021-sample.sqlite"
    duckdb_path = tmp_path / "ferc1-2021-sample.duckdb"
    metadata = tmp_path / "metadata.json"
    datapackage = tmp_path / "datapackage.json"
    log_file = tmp_path / "log.log"
    data_dir = test_dir / "integration" / "data"

    ret = script_runner.run(
        [
            "xbrl_extract",
            str(data_dir / "ferc1-xbrl-2021.zip"),
            "--sqlite-path",
            str(sqlite_path),
            "--duckdb-path",
            str(duckdb_path),
            "--taxonomy",
            str(data_dir / "ferc1-xbrl-taxonomies.zip"),
            "--metadata-path",
            str(metadata),
            "--datapackage-path",
            str(datapackage),
            "--logfile",
            str(log_file),
        ]
    )

    assert ret.success

    # Sanity check the sqlite/duckdb outputs
    with (
        duckdb.connect(sqlite_path) as sqlite_conn,
        duckdb.connect(duckdb_path) as duckdb_conn,
    ):
        # Check for tables that only exist in either sqlite/duckdb but not both
        sqlite_tables = _get_tables(sqlite_conn)
        duckdb_tables = _get_tables(duckdb_conn)

        extra_sqlite_tables = sqlite_tables - duckdb_tables
        extra_duckdb_tables = duckdb_tables - sqlite_tables

        assert extra_sqlite_tables == set()
        assert extra_duckdb_tables == set()

        # Check for empty tables in either output
        empty_sqlite_tables = _find_empty_tables(sqlite_conn, sqlite_tables)
        empty_duckdb_tables = _find_empty_tables(duckdb_conn, duckdb_tables)

        assert empty_sqlite_tables == []
        assert empty_duckdb_tables == []

        # Check that tables are identical
        # SQLite/duckdb have nuanced dtype differences, so ignore types
        for table in sorted(sqlite_tables):
            pd.testing.assert_frame_equal(
                _get_sqlite_df(sqlite_conn, table),
                duckdb_conn.table(table).df(),
                check_like=True,
                check_dtype=False,
                check_exact=True,
            )


@pytest.mark.script_launch_mode("inprocess")
def test_extract_example_filings_bad_form(script_runner, tmp_path, test_dir):
    """Test the XBRL extraction on the example filings.

    Should fail, because of a nonexistent form number.

    """
    out_db = tmp_path / "ferc1-2021-sample.sqlite"
    metadata = tmp_path / "metadata.json"
    datapackage = tmp_path / "datapackage.json"
    log_file = tmp_path / "log.log"
    data_dir = test_dir / "integration" / "data"

    ret = script_runner.run(
        [
            "xbrl_extract",
            str(data_dir / "ferc1-xbrl-2021.zip"),
            str(out_db),
            "--form-number",
            "666",
            "--metadata-path",
            str(metadata),
            "--datapackage-path",
            str(datapackage),
            "--logfile",
            str(log_file),
        ]
    )

    assert not ret.success
