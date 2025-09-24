"""A command line interface (CLI) to the xbrl extractor."""

import argparse
import io
import logging
import sys
from pathlib import Path

import coloredlogs
import duckdb
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ferc_xbrl_extractor import xbrl
from ferc_xbrl_extractor.helpers import get_logger


def parse():
    """Process base commands from the CLI."""
    parser = argparse.ArgumentParser(description="Extract data from XBRL filings")
    parser.add_argument(
        "filings",
        nargs="+",
        help="Path to a single xbrl filing, or a directory of xbrl filings",
        type=Path,
    )
    parser.add_argument(
        "--sqlite-path",
        default="ferc-xbrl.sqlite",
        help="Path to SQLite DB to write extracted XBRL data.",
        type=Path,
    )
    parser.add_argument(
        "--duckdb-path",
        default=None,
        help="Path to duckdb DB to write extracted XBRL data.",
        type=Path,
    )
    parser.add_argument(
        "-s",
        "--datapackage-path",
        default=None,
        type=Path,
        help="Generate frictionless datapackage descriptor, and write to JSON file at specified path.",
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        default=None,
        type=int,
        help="Specify number of instances to be processed at a time(defaults to one large batch)",
    )
    parser.add_argument(
        "-w",
        "--workers",
        default=None,
        type=int,
        help="Specify number of workers in pool (will attempt to choose a reasonable default if not specified)",
    )
    parser.add_argument(
        "-t",
        "--taxonomy",
        default=None,
        help="Specify path to archive of all taxonomies.",
    )
    parser.add_argument(
        "-f",
        "--form-number",
        default=1,
        type=int,
        help="Specify form number to choose taxonomy used to generate output schema (if a taxonomy is explicitly specified that will override this parameter). Form number is also used for setting the name of the datapackage descriptor if requested.",
    )
    parser.add_argument(
        "-m",
        "--metadata-path",
        default=None,
        type=Path,
        help="Specify path to output metadata extracted taxonomy. Metadata will not be extracted if no path is specified.",
    )
    parser.add_argument(
        "--loglevel",
        help="Set log level (valid arguments include DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        default="INFO",
    )
    parser.add_argument("--logfile", help="Path to logfile", type=Path, default=None)

    parser.add_argument(
        "--instance-pattern",
        help="Regex pattern for filing name - if not provided, defaults to '' which matches all.",
        default=r"",
    )

    parser.add_argument(
        "--requested-tables",
        help="Table names to extract - if none, will default to all. Includes the _duration/_instant suffix.",
        nargs="+",
        default=None,
    )

    return parser.parse_args()


def write_to_sqlite(sqlite_engine: Engine, table_name: str, table_data: pd.DataFrame):
    """Write one table to a SQLite database."""
    # Write to SQLite
    with sqlite_engine.begin() as sqlite_conn:
        table_data.to_sql(table_name, sqlite_conn, if_exists="replace")


def write_to_duckdb(duckdb_path: str, table_name: str, table_data: pd.DataFrame):
    """Write one table to a duckdb database."""
    with duckdb.connect(duckdb_path) as duckdb_conn:
        duckdb_conn.execute(
            f"CREATE TABLE OR REPLACE {table_name} AS SELECT * FROM table_data"  # noqa: S608
        )


def load_extracted(
    extracted: xbrl.ExtractOutput,
    sqlite_uri: str,
    duckdb_path: str | None,
) -> None:
    """Write extracted data to SQLite/Duckdb databases."""
    engine = create_engine(sqlite_uri)
    for table_name, data in extracted.table_data.items():
        # Loop through tables and write to database
        if not data.empty:
            write_to_sqlite(engine, table_name, data)

            # Write to duckdb if passed a path to duckdb
            if duckdb_path is not None:
                write_to_duckdb(duckdb_path, table_name, data)


def run_main(
    filings: list[Path] | list[io.BytesIO],
    taxonomy: str | Path | io.BytesIO,
    sqlite_path: Path,
    duckdb_path: Path | None,
    form_number: int | None,
    metadata_path: Path | None,
    datapackage_path: Path | None,
    workers: int | None,
    batch_size: int | None,
    loglevel: str,
    logfile: Path | None,
    requested_tables: list[str] | None = None,
    instance_pattern: str = r"",
):
    """Log setup, taxonomy finding, and SQL IO."""
    logger = get_logger("ferc_xbrl_extractor")
    logger.setLevel(loglevel)
    log_format = "%(asctime)s [%(levelname)8s] %(name)s:%(lineno)s %(message)s"
    coloredlogs.install(fmt=log_format, level=loglevel, logger=logger)

    sqlite_uri = f"sqlite:///{sqlite_path.absolute()}"

    if logfile:
        file_logger = logging.FileHandler(logfile)
        file_logger.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_logger)

    extracted = xbrl.extract(
        taxonomy_source=taxonomy,
        form_number=form_number,
        db_uri=sqlite_uri,
        datapackage_path=datapackage_path,
        metadata_path=metadata_path,
        filings=filings,
        workers=workers,
        batch_size=batch_size,
        requested_tables=requested_tables,
        instance_pattern=instance_pattern,
    )
    # Save extracted data in SQLite/duckdb
    load_extracted(extracted, sqlite_uri, duckdb_path)


def main():
    """Parse arguments and pass to run_main."""
    return run_main(**vars(parse()))


if __name__ == "__main__":
    sys.exit(main())
