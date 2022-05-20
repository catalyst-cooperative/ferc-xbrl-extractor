"""XBRL extractor."""
import logging
import math
from concurrent.futures import ProcessPoolExecutor as Executor
from functools import cache, partial
from typing import Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import sqlalchemy as sa

from .datapackage import Datapackage
from .instance import parse
from .taxonomy import Taxonomy


def extract(
    instance_paths: List[Tuple[str, int]],
    engine: sa.engine.Engine,
    batch_size: Optional[int] = None,
    workers: Optional[int] = None,
    write_batch: bool = False,
    save_metadata: bool = False,
):
    """
    Extract data from all specified XBRL filings.

    Args:
        instance_paths: List of all XBRL filings to extract.
        engine: SQLite connection.
        batch_size: Number of filings to process before writing to DB.
        threads: Number of threads to create for parsing filings.
        save_metadata: Save XBRL references to JSON file.
    """
    logger = logging.getLogger(__name__)

    num_instances = len(instance_paths)
    if not batch_size:
        batch_size = num_instances // workers if workers else num_instances

    num_batches = math.ceil(num_instances / batch_size)

    with Executor(max_workers=workers) as executor:
        # Bind arguments generic to all filings
        process_batches = partial(
            process_batch,
            save_metadata=save_metadata,
        )

        batched_instances = np.array_split(
            instance_paths, math.ceil(num_instances / batch_size)
        )

        # Use thread pool to extract data from all filings in parallel
        results = executor.map(process_batches, batched_instances)

        # Write extracted data to database
        for i, batch in enumerate(results):
            logger.info(f"Finished batch {i}/{num_batches}")

            # Loop through tables and write to database
            for key, df in batch.items():
                if not df.empty:
                    df.to_sql(key, engine, if_exists="append")


def process_batch(instances: Iterable[Tuple[str, str]], save_metadata: bool = False):
    """
    Extract data from one batch of instances.

    Splitting instances into batches significantly improves multiprocessing
    performance. This is done explicitly rather than using ProcessPoolExecutor's
    chunk_size option so dataframes within the batch can be concatenated prior to
    returning to the parent process.

    Args:
        instances: Iterator of instances.
        save_metadata: Save XBRL references in JSON file.
    """
    dfs = {}
    for instance in instances:
        instance_dfs = process_instance(instance, save_metadata)

        for key, df in instance_dfs.items():
            if key not in dfs:
                dfs[key] = []

            dfs[key].append(df)

    dfs = {key: pd.concat(df_list) for key, df_list in dfs.items()}

    return dfs


def process_instance(
    instance: Tuple[str, str],
    save_metadata: bool = False,
):
    """
    Extract data from a single XBRL filing.

    Args:
        instance: Tuple of path to instance and filing_name for instance.
        save_metadata: Save XBRL references in JSON file.
    """
    logger = logging.getLogger(__name__)
    instance_path, filing_name = instance
    contexts, facts, tax_url = parse(instance_path)

    tables = get_fact_tables(tax_url, save_metadata)

    logger.info(f"Extracting {instance_path}")

    dfs = {}
    for key, table in tables.items():
        dfs[key] = table.construct_dataframe(facts, contexts, filing_name)

    return dfs


@cache
def get_fact_tables(
    taxonomy_path: str,
    save_metadata: bool = False,
):
    """
    Parse taxonomy from URL.

    Caches results so each taxonomy is only retrieved and parsed once.

    Args:
        taxonomy_path: URL of taxonomy.
        save_metadata: Save XBRL references in JSON file.

    Returns:
        Dictionary mapping to table names to structure.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Parsing taxonomy from {taxonomy_path}")
    taxonomy = Taxonomy.from_path(taxonomy_path, save_metadata)
    datapackage = Datapackage.from_taxonomy(taxonomy)

    if save_metadata:
        json = datapackage.json(by_alias=True)
        with open("datapackage.json", "w") as f:
            f.write(json)

    return datapackage.get_fact_tables()
