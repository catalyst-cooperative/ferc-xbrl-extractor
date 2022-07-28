"""XBRL extractor."""
import math
from concurrent.futures import ProcessPoolExecutor as Executor
from functools import partial
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
import sqlalchemy as sa

from .datapackage import Datapackage, FactTable
from .helpers import get_logger
from .instance import InstanceBuilder
from .taxonomy import Taxonomy


def extract(
    instances: List[InstanceBuilder],
    engine: sa.engine.Engine,
    taxonomy: str,
    batch_size: Optional[int] = None,
    workers: Optional[int] = None,
    save_metadata: bool = False,
):
    """
    Extract data from all specified XBRL filings.

    Args:
        instance_paths: List of all XBRL instances to extract.
        engine: SQLite connection.
        taxonomy: Specify taxonomy used to create structure of output DB.
        batch_size: Number of filings to process before writing to DB.
        workers: Number of threads to create for parsing filings.
        save_metadata: Save XBRL references to JSON file.
    """
    logger = get_logger(__name__)

    num_instances = len(instances)
    if not batch_size:
        batch_size = num_instances // workers if workers else num_instances

    num_batches = math.ceil(num_instances / batch_size)

    tables = get_fact_tables(taxonomy, str(engine.url), save_metadata)

    with Executor(max_workers=workers) as executor:
        # Bind arguments generic to all filings
        process_batches = partial(
            process_batch,
            tables=tables,
            save_metadata=save_metadata,
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
    tables: Dict[str, FactTable],
    save_metadata: bool = False,
):
    """
    Extract data from one batch of instances.

    Splitting instances into batches significantly improves multiprocessing
    performance. This is done explicitly rather than using ProcessPoolExecutor's
    chunk_size option so dataframes within the batch can be concatenated prior to
    returning to the parent process.

    Args:
        instances: Iterator of instances.
        taxonomy: Specify taxonomy used to create structure of output DB.
        save_metadata: Save XBRL references in JSON file.
    """
    dfs = {}
    for instance in instances:
        instance_dfs = process_instance(instance, tables, save_metadata)

        for key, df in instance_dfs.items():
            if key not in dfs:
                dfs[key] = []

            dfs[key].append(df)

    dfs = {key: pd.concat(df_list) for key, df_list in dfs.items()}

    return dfs


def process_instance(
    instance_parser: InstanceBuilder,
    tables: Dict[str, FactTable],
    save_metadata: bool = False,
):
    """
    Extract data from a single XBRL filing.

    Args:
        instance: Tuple of path to instance and filing_name for instance.
        taxonomy: Specify taxonomy used to create structure of output DB.
        save_metadata: Save XBRL references in JSON file.
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
    db_path: str,
    save_metadata: bool = False,
):
    """
    Parse taxonomy from URL.

    Caches results so each taxonomy is only retrieved and parsed once.

    Args:
        taxonomy_path: URL of taxonomy.
        db_path: Path to database used for constructing datapackage descriptor.
        save_metadata: Save XBRL references in JSON file.

    Returns:
        Dictionary mapping to table names to structure.
    """
    logger = get_logger(__name__)
    logger.info(f"Parsing taxonomy from {taxonomy_path}")
    taxonomy = Taxonomy.from_path(taxonomy_path, save_metadata)
    datapackage = Datapackage.from_taxonomy(taxonomy, db_path)

    if save_metadata:
        json = datapackage.json(by_alias=True)
        with open("datapackage.json", "w") as f:
            f.write(json)

    return datapackage.get_fact_tables()
