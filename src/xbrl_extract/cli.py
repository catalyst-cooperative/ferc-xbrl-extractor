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
        "-c",
        "--clobber",
        action="store_true",
        default=False,
        help="Clobber existing outputs if they exist"
    )

    return parser.parse_args()


def instance_iter(instance_path: Path, taxonomy: Taxonomy):
    ALLOWABLE_SUFFIXES = [".xbrl"]

    if not instance_path.exists():
        raise ValueError("Must provide valid path to XBRL instance or directory"
                         "of XBRL instances.")

    if instance_path.is_file():
        if instance_path.suffix not in ALLOWABLE_SUFFIXES:
            raise ValueError("Must provide valid path to XBRL instance or "
                             "directory of XBRL instances.")

        yield str(instance_path)
    elif instance_path.is_dir():
        for instance in instance_path.iterdir():
            if instance.suffix not in ALLOWABLE_SUFFIXES:
                continue

            yield str(instance)


def main():
    """Parse CLI args and extract XBRL data."""
    args = parse_main()

    taxonomy = Taxonomy.from_path(args.taxonomy_path)

    engine = create_engine(f"sqlite:///{args.to_sql}") if args.to_sql else None

    instances = instance_iter(
        Path(args.instance_path),
        taxonomy,
    )

    xbrl.extract(
        taxonomy,
        instances,
        engine,
    )


if __name__ == "__main__":
    sys.exit(main())
