"""A command line interface (CLI) to the xbrl extractor."""
import argparse
import sys
from pathlib import Path
from sqlalchemy import create_engine
from xbrl_extract.taxonomy import Taxonomy
from xbrl_extract import xbrl


def parse_main():
    """
    Process base commands from the CLI. More options can be added as necessary.
    """
    parser = argparse.ArgumentParser(description="Extract data from XBRL filings")
    parser.add_argument(
        "taxonomy_path",
        help="File path or url to an XBRL taxonomy"
    )
    parser.add_argument(
        "instance_path",
        help="Path to a single xbrl filing, or a directory of xbrl filings",
    )
    parser.add_argument(
        "--to-sql",
        default=False,
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
        default=1,
        type=int,
        help="Specify number of instances to be processed at a time"
    )
    parser.add_argument(
        "-t",
        "--threads",
        default=None,
        type=int,
        help="Specify number of threads in pool (defaults to `os.cpu_count()`)"
    )

    return parser.parse_args()


def get_instances(instance_path: Path, taxonomy: Taxonomy):
    ALLOWABLE_SUFFIXES = [".xbrl", ".xml"]

    if not instance_path.exists():
        raise ValueError("Must provide valid path to XBRL instance or directory"
                         "of XBRL instances.")

    if instance_path.is_file():
        if instance_path.suffix not in ALLOWABLE_SUFFIXES:
            raise ValueError("Must provide valid path to XBRL instance or "
                             "directory of XBRL instances.")

        return [(str(instance_path), 0)]
    elif instance_path.is_dir():
        return [(str(instance), i)
                for i, instance in enumerate(instance_path.iterdir())
                if instance.suffix in ALLOWABLE_SUFFIXES]


def main():
    """Parse CLI args and extract XBRL data."""
    args = parse_main()

    taxonomy = Taxonomy.from_path(args.taxonomy_path, args.save_metadata)

    engine = create_engine(f"sqlite:///{args.to_sql}") if args.to_sql else None

    instances = get_instances(
        Path(args.instance_path),
        taxonomy,
    )

    xbrl.extract(
        taxonomy,
        instances,
        engine,
        args.batch_size,
        args.threads,
        args.gen_filing_id,
    )


if __name__ == "__main__":
    sys.exit(main())
