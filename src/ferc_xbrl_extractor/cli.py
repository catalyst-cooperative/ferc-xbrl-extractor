"""A command line interface (CLI) to the xbrl extractor."""

import argparse
import io
import logging
import sys
from pathlib import Path

import coloredlogs
from sqlalchemy import create_engine

from ferc_xbrl_extractor import helpers, xbrl
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
        "-d",
        "--db_path",
        default="ferc-xbrl.sqlite",
        help="Store data in sqlite database specified in argument",
    )
    parser.add_argument(
        "-s",
        "--datapackage-path",
        default=None,
        type=Path,
        help="Generate frictionless datapackage descriptor, and write to JSON file at specified path.",
    )
    parser.add_argument(
        "-c",
        "--clobber",
        action="store_true",
        default=False,
        help="Clobber existing outputs if they exist",
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


def run_main(
    filings: list[Path] | list[io.BytesIO],
    db_path: Path,
    clobber: bool,
    taxonomy: str | Path | io.BytesIO,
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

    if logfile:
        file_logger = logging.FileHandler(logfile)
        file_logger.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_logger)

    db_uri = f"sqlite:///{db_path}"
    engine = create_engine(db_uri)

    if clobber:
        helpers.drop_tables(engine)

    extracted = xbrl.extract(
        taxonomy_source=taxonomy,
        form_number=form_number,
        db_uri=db_uri,
        datapackage_path=datapackage_path,
        metadata_path=metadata_path,
        filings=filings,
        workers=workers,
        batch_size=batch_size,
        requested_tables=requested_tables,
        instance_pattern=instance_pattern,
    )

    with engine.begin() as conn:
        for table_name, data in extracted.table_data.items():
            # Loop through tables and write to database
            if not data.empty:
                data.to_sql(table_name, conn, if_exists="append")


def main():
    """Parse arguments and pass to run_main."""
    return run_main(**vars(parse()))


if __name__ == "__main__":
    sys.exit(main())
