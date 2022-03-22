"""A command line interface (CLI) to the xbrl extractor."""
import argparse
import sys
from pathlib import Path
from sqlalchemy import create_engine
from xbrl_extract.xbrl import Instance, Taxonomy


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
    parser.add_argument(
        "--entity-id",
        default=None,
        help="Specify entity_id to be used for a filings processed"
    )
    parser.add_argument(
        "--entity-id-fact",
        default=None,
        help="Specify fact to be extracted and used as entity_id"
    )

    return parser.parse_args()


def instance_iter(
    instance_path: Path,
    taxonomy: Taxonomy,
    entity_id=None,
    entity_id_fact=None
):
    ALLOWABLE_SUFFIXES = [".xbrl"]

    if not instance_path.exists():
        raise ValueError("Must provide valid path to XBRL instance or directory"
                         "of XBRL instances.")

    if instance_path.is_file():
        if instance_path.suffix not in ALLOWABLE_SUFFIXES:
            raise ValueError("Must provide valid path to XBRL instance or "
                             "directory of XBRL instances.")

        yield Instance(taxonomy, str(instance_path), entity_id, entity_id_fact)
    elif instance_path.is_dir():
        for instance in instance_path.iterdir():
            if instance.suffix not in ALLOWABLE_SUFFIXES:
                continue

            yield Instance(taxonomy, str(instance), entity_id, entity_id_fact)


def main():
    """Parse CLI args and extract XBRL data."""
    args = parse_main()

    print(args.taxonomy_path)
    taxonomy = Taxonomy.from_path(args.taxonomy_path)

    engine = create_engine(f"sqlite:///{args.to_sql}") if args.to_sql else None

    instances = instance_iter(
        Path(args.instance_path),
        taxonomy,
        args.entity_id,
        args.entity_id_fact
    )

    for instance in instances:
        print(instance.entity_id)
        if args.to_sql:
            instance.to_sql(engine)


if __name__ == "__main__":
    sys.exit(main())
