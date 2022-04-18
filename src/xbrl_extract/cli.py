"""A command line interface (CLI) to the xbrl extractor."""
import argparse
import sys
from pathlib import Path
from sqlalchemy import create_engine
from xbrl_extract import xbrl


def parse_main():
    """Process base commands from the CLI."""
    parser = argparse.ArgumentParser(description="Extract data from XBRL filings")
    parser.add_argument(
        "instance_path",
        help="Path to a single xbrl filing, or a directory of xbrl filings",
    )
    parser.add_argument(
        "sql_path",
        help="Store data in sqlite database specified in argument"
    )
    parser.add_argument(
        "--gen-filing-id",
        default=False,
        action="store_true",
        help="Generate a unique ID for each filing processed (starts at 0 and increments)"
    )
    parser.add_argument(
        "--save-metadata",
        default='',
        help="Save metadata defined in XBRL references"
    )
    parser.add_argument(
        "-c",
        "--clobber",
        action="store_true",
        default=False,
        help="Clobber existing outputs if they exist"
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        default=None,
        type=int,
        help="Specify number of instances to be processed at a time(defaults to one large batch)"
    )
    parser.add_argument(
        "-t",
        "--threads",
        default=None,
        type=int,
        help="Specify number of threads in pool (defaults to `os.cpu_count()`)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Print logging messages to stdout",
    )
    parser.add_argument(
        "--loglevel",
        help="Set log level",
        default="INFO",
    )

    return parser.parse_args()


def get_instances(instance_path: Path):
    """Get list of instances from specified path."""
    ALLOWABLE_SUFFIXES = [".xbrl", ".xml"]

    if not instance_path.exists():
        raise ValueError("Must provide valid path to XBRL instance or directory"
                         "of XBRL instances.")

    # Single instance
    if instance_path.is_file():
        if instance_path.suffix not in ALLOWABLE_SUFFIXES:
            raise ValueError("Must provide valid path to XBRL instance or "
                             "directory of XBRL instances.")

        return [(str(instance_path), 0)]
    # Directory of instances
    elif instance_path.is_dir():
        instances = [str(instance) for instance in instance_path.iterdir()
                     if instance.suffix in ALLOWABLE_SUFFIXES]
        return [(instance, i) for i, instance in enumerate(sorted(instances))]


def main():
    """CLI for extracting data fro XBRL filings."""
    args = parse_main()

    engine = create_engine(f"sqlite:///{args.sql_path}")

    instances = get_instances(
        Path(args.instance_path),
    )

    xbrl.extract(
        instances,
        engine,
        args.batch_size,
        args.threads,
        args.gen_filing_id,
        args.save_metadata,
        args.verbose,
        args.loglevel
    )


if __name__ == "__main__":
    sys.exit(main())
