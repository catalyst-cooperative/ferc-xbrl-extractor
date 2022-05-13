"""A command line interface (CLI) to the xbrl extractor."""
import argparse
import logging
import sys
from pathlib import Path

import coloredlogs
from sqlalchemy import create_engine

from xbrl_extract import helpers, xbrl


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
        (str(instance), instance.name.rstrip(instance.suffix))
        for instance in sorted(instances)
        if instance.suffix in allowable_suffixes
    ]


def main():
    """CLI for extracting data fro XBRL filings."""
    args = parse_main()

    logger = logging.getLogger("xbrl_extract")
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

    instances = get_instances(
        Path(args.instance_path),
    )

    xbrl.extract(
        instances,
        engine,
        batch_size=args.batch_size,
        workers=args.workers,
        save_metadata=args.save_metadata,
    )


if __name__ == "__main__":
    sys.exit(main())
