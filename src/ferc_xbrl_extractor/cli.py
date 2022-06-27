"""A command line interface (CLI) to the xbrl extractor."""
import argparse
import logging
import sys
from pathlib import Path

import coloredlogs
from sqlalchemy import create_engine

from ferc_xbrl_extractor import helpers, xbrl
from ferc_xbrl_extractor.helpers import get_logger
from ferc_xbrl_extractor.instance import InstanceBuilder

TAXONOMY_MAP = {
    1: "https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd",
    2: "https://eCollection.ferc.gov/taxonomy/form2/2022-01-01/form/form2/form-2_2022-01-01.xsd",
    6: "https://eCollection.ferc.gov/taxonomy/form6/2022-01-01/form/form6/form-6_2022-01-01.xsd",
    60: "https://eCollection.ferc.gov/taxonomy/form60/2022-01-01/form/form60/form-60_2022-01-01.xsd",
    714: "https://eCollection.ferc.gov/taxonomy/form714/2022-01-01/form/form714/form-714_2022-01-01.xsd",
}


def parse_main():
    """Process base commands from the CLI."""
    parser = argparse.ArgumentParser(description="Extract data from XBRL filings")
    parser.add_argument(
        "instance_path",
        help="Path to a single xbrl filing, or a directory of xbrl filings",
    )
    parser.add_argument(
        "sql_path", help="Store data in sqlite database specified in argument"
    )
    parser.add_argument(
        "-s",
        "--save-metadata",
        default=None,
        help="Save metadata defined in XBRL references",
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
        help="Specify form number to choose taxonomy used to generate output schema (if a taxonomy is explicitly specified that will override this parameter)",
    )
    parser.add_argument(
        "--loglevel",
        help="Set log level (valid arguments include DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        default="INFO",
    )
    parser.add_argument("--logfile", help="Path to logfile", default=None)

    return parser.parse_args()


def get_instances(instance_path: Path):
    """
    Get list of instances from specified path.

    Args:
        instance_path: Path to one or more XBRL filings.
    Returns:
        List of tuples containing the path to an instance and the name of the filing.
    """
    allowable_suffixes = [".xbrl", ".xml"]

    if not instance_path.exists():
        raise ValueError(
            "Must provide valid path to XBRL instance or directory" "of XBRL instances."
        )

    # Single instance
    if instance_path.is_file():
        instances = [instance_path]
    # Directory of instances
    else:
        # Must be either a directory or file
        assert instance_path.is_dir()
        instances = instance_path.iterdir()

    return [
        InstanceBuilder(str(instance), instance.name.rstrip(instance.suffix))
        for instance in sorted(instances)
        if instance.suffix in allowable_suffixes
    ]


def main():
    """CLI for extracting data fro XBRL filings."""
    args = parse_main()

    logger = get_logger("ferc_xbrl_extractor")
    logger.setLevel(args.loglevel)
    log_format = "%(asctime)s [%(levelname)8s] %(name)s:%(lineno)s %(message)s"
    coloredlogs.install(fmt=log_format, level=args.loglevel, logger=logger)

    if args.logfile:
        file_logger = logging.FileHandler(args.logfile)
        file_logger.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_logger)

    engine = create_engine(f"sqlite:///{args.sql_path}")

    if args.clobber:
        helpers.drop_tables(engine)

    # Get taxonomy URL
    if args.taxonomy:
        taxonomy = args.taxonomy
    else:
        if args.form_number not in TAXONOMY_MAP:
            raise ValueError(
                f"Form number {args.form_number} is not valid. Supported form numbers include {list(TAXONOMY_MAP.keys())}"
            )

        # Get most recent taxonomy for specified form number
        taxonomy = TAXONOMY_MAP[args.form_number]

    instances = get_instances(
        Path(args.instance_path),
    )

    xbrl.extract(
        instances,
        engine,
        taxonomy,
        batch_size=args.batch_size,
        workers=args.workers,
        save_metadata=args.save_metadata,
    )


if __name__ == "__main__":
    sys.exit(main())
