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

TAXONOMY_MAP = {
    1: "https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd",
    2: "https://eCollection.ferc.gov/taxonomy/form2/2022-01-01/form/form2/form-2_2022-01-01.xsd",
    6: "https://eCollection.ferc.gov/taxonomy/form6/2022-01-01/form/form6/form-6_2022-01-01.xsd",
    60: "https://eCollection.ferc.gov/taxonomy/form60/2022-01-01/form/form60/form-60_2022-01-01.xsd",
    714: "https://eCollection.ferc.gov/taxonomy/form714/2022-01-01/form/form714/form-714_2022-01-01.xsd",
}


def parse():
    """Process base commands from the CLI."""
    parser = argparse.ArgumentParser(description="Extract data from XBRL filings")
    parser.add_argument(
        "instance_path",
        help="Path to a single xbrl filing, or a directory of xbrl filings",
        type=Path,
    )
    parser.add_argument(
        "sql_path", help="Store data in sqlite database specified in argument"
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
        help="Specify taxonomy used create structure of final database",
    )
    parser.add_argument(
        "-f",
        "--form-number",
        default=1,
        type=int,
        help="Specify form number to choose taxonomy used to generate output schema (if a taxonomy is explicitly specified that will override this parameter). Form number is also used for setting the name of the datapackage descriptor if requested.",
    )
    parser.add_argument(
        "-a",
        "--entry-point",
        default=None,
        type=Path,
        help="Specify path to taxonomy entry point within a zipfile archive. This is a relative path within the taxonomy. If specified, `taxonomy` must be set to point to the zipfile location on the local file system.",
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

    return parser.parse_args()


def run_main(
    instance_path: Path | io.BytesIO,
    sql_path: Path,
    clobber: bool,
    taxonomy: Path | io.BytesIO | None,
    entry_point: Path,
    form_number: int | None,
    metadata_path: Path | None,
    datapackage_path: Path | None,
    workers: int | None,
    batch_size: int | None,
    loglevel: str,
    logfile: Path | None,
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

    db_uri = f"sqlite:///{sql_path}"
    engine = create_engine(db_uri)

    if clobber:
        helpers.drop_tables(engine)

    # Verify taxonomy is set if archive_path is set
    if entry_point and not taxonomy:
        raise ValueError("taxonomy must be set if archive_path is given.")

    # Get taxonomy URL
    if taxonomy is None:
        if form_number not in TAXONOMY_MAP:
            raise ValueError(
                f"Form number {form_number} is not valid. Supported form numbers include {list(TAXONOMY_MAP.keys())}"
            )
        # Get most recent taxonomy for specified form number
        taxonomy = TAXONOMY_MAP[form_number]

    extracted = xbrl.extract(
        taxonomy_source=taxonomy,
        form_number=form_number,
        db_uri=db_uri,
        entry_point=entry_point,
        datapackage_path=datapackage_path,
        metadata_path=metadata_path,
        instance_path=instance_path,
        workers=workers,
        batch_size=batch_size,
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
