"""XBRL extractor."""
import math
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor as Executor
from functools import partial

import numpy as np
import pandas as pd
import sqlalchemy as sa
from frictionless import Package
from lxml.etree import XMLSyntaxError  # nosec: B410

from ferc_xbrl_extractor.datapackage import Datapackage, FactTable
from ferc_xbrl_extractor.helpers import get_logger
from ferc_xbrl_extractor.instance import InstanceBuilder
from ferc_xbrl_extractor.taxonomy import Taxonomy


def extract(
    instances: list[InstanceBuilder],
    engine: sa.engine.Engine,
    taxonomy: str,
    form_number: int,
    archive_file_path: str | None = None,
    requested_tables: set[str] | None = None,
    batch_size: int | None = None,
    workers: int | None = None,
    datapackage_path: str | None = None,
    metadata_path: str | None = None,
) -> None:
    """Extract data from all specified XBRL filings.

    Args:
        instances: A list of InstanceBuilder objects used for parsing XBRL filings.
        engine: SQLite connection to output database.
        form_number: FERC Form number (can be 1, 2, 6, 60, 714).
        taxonomy: Specify taxonomy used to create structure of output DB.
        archive_file_path: Path to taxonomy entry point within archive. If not None,
                then `taxonomy` should be a path to zipfile, not a URL.
        requested_tables: Optionally specify the set of tables to extract.
                If None, all possible tables will be extracted.
        batch_size: Number of filings to process before writing to DB.
        workers: Number of threads to create for parsing filings.
        datapackage_path: Create frictionless datapackage and write to specified path as JSON file.
                          If path is None no datapackage descriptor will be saved.
        metadata_path: Path to metadata json file to output taxonomy metadata.
    """
    logger = get_logger(__name__)

    num_instances = len(instances)
    if not batch_size:
        batch_size = num_instances // workers if workers else num_instances

    num_batches = math.ceil(num_instances / batch_size)

    tables = get_fact_tables(
        taxonomy,
        form_number,
        str(engine.url),
        archive_file_path=archive_file_path,
        tables=requested_tables,
        datapackage_path=datapackage_path,
        metadata_path=metadata_path,
    )

    with Executor(max_workers=workers) as executor:
        # Bind arguments generic to all filings
        process_batches = partial(
            process_batch,
            tables=tables,
        )

        batched_instances = np.array_split(
            instances, math.ceil(num_instances / batch_size)
        )

        # Use thread pool to extract data from all filings in parallel
        results = executor.map(process_batches, batched_instances)

        # Write extracted data to database
        for i, batch in enumerate(results):
            logger.info(f"Finished batch {i + 1}/{num_batches}")

            # Loop through tables and write to database
            with engine.begin() as conn:
                for key, df in batch.items():
                    if not df.empty:
                        df.to_sql(key, conn, if_exists="append")


def process_batch(
    instances: Iterable[InstanceBuilder],
    tables: dict[str, FactTable],
) -> dict[str, pd.DataFrame]:
    """Extract data from one batch of instances.

    Splitting instances into batches significantly improves multiprocessing
    performance. This is done explicitly rather than using ProcessPoolExecutor's
    chunk_size option so dataframes within the batch can be concatenated prior to
    returning to the parent process.

    Args:
        instances: Iterator of instances.
        tables: Dictionary mapping table names to FactTable objects describing table structure.
    """
    logger = get_logger(__name__)

    dfs: dict[str, pd.DataFrame] = {}
    for instance in instances:
        # Parse XBRL instance. Log/skip if file is empty
        try:
            instance_dfs = process_instance(instance, tables)
        except XMLSyntaxError:
            logger.info(f"XBRL filing {instance.name} is empty. Skipping.")
            continue

        for key, df in instance_dfs.items():
            if key not in dfs:
                dfs[key] = []

            dfs[key].append(df)

    dfs = {key: pd.concat(df_list) for key, df_list in dfs.items()}

    return dfs


def process_instance(
    instance_parser: InstanceBuilder,
    tables: dict[str, FactTable],
) -> dict[str, pd.DataFrame]:
    """Extract data from a single XBRL filing.

    This function will use the InstanceBuilder object to parse
    a single XBRL filing. It then iterates through requested tables
    and populates them with data extracted from the filing.

    Args:
        instance_parser: A single InstanceBuilder object used to parse an XBRL filing.
        tables: Dictionary mapping table names to FactTable objects describing table structure.
    """
    logger = get_logger(__name__)
    instance = instance_parser.parse()

    logger.info(f"Extracting {instance.filing_name}")

    dfs = {}
    for key, table in tables.items():
        dfs[key] = table.construct_dataframe(instance)

    return dfs


def get_fact_tables(
    taxonomy_path: str,
    form_number: int,
    db_path: str,
    archive_file_path: str | None = None,
    tables: set[str] | None = None,
    datapackage_path: str | None = None,
    metadata_path: str | None = None,
) -> dict[str, FactTable]:
    """Parse taxonomy from URL.

    XBRL defines 'fact tables' that groups related facts. These fact
    tables are used directly to create the tables that will make up the
    output SQLite database, and their structure. The output of this function
    is a dictionary that maps table names to 'FactTable' objects that specify
    their structure.

    This function will also output a json file containing a Frictionless
    Data-Package descriptor describing the output database if requested.

    Args:
        taxonomy_path: URL of taxonomy.
        form_number: FERC Form number (can be 1, 2, 6, 60, 714).
        db_path: Path to database used for constructing datapackage descriptor.
        archive_file_path: Path to taxonomy entry point within archive. If not None,
                then `taxonomy` should be a path to zipfile, not a URL.
        tables: Optionally specify the set of tables to extract.
                If None, all possible tables will be extracted.
        datapackage_path: Create frictionless datapackage and write to specified path as JSON file.
                          If path is None no datapackage descriptor will be saved.
        metadata_path: Path to metadata json file to output taxonomy metadata.

    Returns:
        Dictionary mapping to table names to structure.
    """
    logger = get_logger(__name__)
    logger.info(f"Parsing taxonomy from {taxonomy_path}")
    taxonomy = Taxonomy.from_path(
        taxonomy_path, archive_file_path=archive_file_path, metadata_path=metadata_path
    )
    datapackage = Datapackage.from_taxonomy(taxonomy, db_path, form_number=form_number)

    if datapackage_path:
        # Verify that datapackage descriptor is valid before outputting
        frictionless_package = Package(descriptor=datapackage.dict(by_alias=True))
        if not frictionless_package.metadata_valid:
            raise RuntimeError("Generated datapackage is invalid")

        # Write to JSON file
        with open(datapackage_path, "w") as f:
            f.write(datapackage.json(by_alias=True))

    return datapackage.get_fact_tables(tables=tables)
