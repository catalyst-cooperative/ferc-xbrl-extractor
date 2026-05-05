"""A command line interface (CLI) to the xbrl extractor."""

import argparse
import io
import json
import logging
import sys
from itertools import chain
from pathlib import Path

import coloredlogs
import duckdb
import pandas as pd
from frictionless import Package
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ferc_xbrl_extractor import xbrl
from ferc_xbrl_extractor.helpers import get_logger


def parse():
    """Process base commands from the CLI."""
    parser = argparse.ArgumentParser(
        description="Extract data from XBRL filings to SQLite or DuckDB."
    )
    parser.add_argument(
        "filings",
        nargs="+",
        help="Path to a single XBRL filing, a directory of XBRL filings, or a zipfile containing XBRL filings.",
        type=Path,
    )
    parser.add_argument(
        "--output-dir",
        help="Path to output directory where parquet directory will end up.",
        type=Path,
    )
    parser.add_argument(
        "--sqlite-path",
        help="Path to SQLite DB to write extracted XBRL data.",
        type=Path,
    )
    parser.add_argument(
        "--duckdb-path",
        help="Path to DuckDB DB to write extracted XBRL data.",
        type=Path,
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        default=None,
        type=int,
        help="Specify number of instances to be processed at a time (defaults to one large batch)",
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
        type=int,
        help="Specify form number to choose taxonomy used to generate output schema (if a taxonomy is explicitly specified that will override this parameter). Form number is also used for setting the name of the datapackage descriptor if requested.",
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
    table_data = table_data.reset_index()
    with duckdb.connect(duckdb_path) as duckdb_conn:
        duckdb_conn.execute(
            f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM table_data"  # noqa: S608
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
    output_dir: Path,
    sqlite_path: Path,
    duckdb_path: Path,
    form_number: int,
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
    datapackage_path = output_dir / f"ferc{form_number}_xbrl_datapackage.json"
    metadata_path = output_dir / f"ferc{form_number}_xbrl_taxonomy_metadata.json"

    if logfile:
        file_logger = logging.FileHandler(logfile)
        file_logger.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_logger)

    # NOTE 2026-04-30: This would flow much better overall if extract was split into two steps:
    #
    # 1. extract taxonomy and metadata
    # 2. read data in from xbrl
    #
    # Then we can do the loading and writing of datapackage.jsons out at the end.
    #
    # CG/DX did not have time or gumption for this refactor but think it would
    # make this easier to work with.
    extracted = xbrl.extract(
        taxonomy_source=taxonomy,
        form_number=form_number,
        db_uri=sqlite_path.absolute().name,
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

    parquet_dir = output_dir / f"ferc{form_number}_xbrl"
    convert_duckdb_into_parquet(duckdb_path=duckdb_path, parquet_dir=parquet_dir)
    datapackage_parquet = convert_and_validate_datapackage_sqlite_to_parquet(
        datapackage_path=datapackage_path
    )
    write_datapackage(datapackage=datapackage_parquet, output_dir=parquet_dir)


def convert_duckdb_into_parquet(duckdb_path: Path, parquet_dir: Path):
    """Convert the duckdb into a directory of parquet files."""
    con = duckdb.connect(duckdb_path)
    tables = con.sql("SHOW TABLES").fetchall()
    # tables is a list of tuples, so condense the list
    tables = chain.from_iterable(tables)
    if not parquet_dir.exists():
        parquet_dir.mkdir(exist_ok=True)
    for table in tables:
        con.execute(
            f"COPY {table} TO '{parquet_dir}/{table}.parquet' (FORMAT parquet);"
        )
    # unfortunately export database sanitizes the table names, which removes the
    # schedule numbers in the table names so we can't use it.
    # con.execute(f"EXPORT DATABASE '{str(parquet_dir)}' (FORMAT PARQUET);")


def convert_and_validate_datapackage_sqlite_to_parquet(datapackage_path: Path) -> dict:
    """Convert the datapackage made for the SQLite files."""
    # read existing datapackage
    with Path(datapackage_path).open() as file:
        datapackage = json.load(file)
    # update paths, remove the dialect, change format + mediatype
    for resource in datapackage["resources"]:
        name = resource["name"]
        resource["path"] = f"{name}.parquet"
        resource["format"] = "parquet"
        resource["mediatype"] = "application/vnd.apache.parquet"
        resource.pop("dialect")

    # Verify that datapackage descriptor is valid before outputting
    report = Package.validate_descriptor(datapackage)
    if not report.valid:
        raise RuntimeError(f"Generated datapackage is invalid - {report.errors}")
    return datapackage


def write_datapackage(datapackage: dict, output_dir: Path):
    """Write datapackage."""
    # Write to JSON file
    with Path(output_dir / "datapackage.json").open(mode="w") as f:
        f.write(json.dumps(datapackage, indent=2))


def main():
    """Parse arguments and pass to run_main."""
    return run_main(**vars(parse()))


if __name__ == "__main__":
    sys.exit(main())
