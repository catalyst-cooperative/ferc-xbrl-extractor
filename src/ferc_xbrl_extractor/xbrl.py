"""XBRL extractor."""
import math
from collections import defaultdict, namedtuple
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor as Executor
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
from frictionless import Package
from lxml.etree import XMLSyntaxError  # nosec: B410

from ferc_xbrl_extractor.datapackage import Datapackage, FactTable
from ferc_xbrl_extractor.helpers import get_logger
from ferc_xbrl_extractor.instance import Instance, get_instances
from ferc_xbrl_extractor.taxonomy import Taxonomy

ExtractOutput = namedtuple(
    "ExtractOutput", ["table_defs", "instances", "table_data", "stats"]
)


def extract(
    instance_path: Path,
    taxonomy_path: Path,
    form_number: int,
    db_uri: str,
    archive_path: Path | None = None,
    datapackage_path: Path | None = None,
    metadata_path: Path | None = None,
    requested_tables: set[str] | None = None,
    workers: int | None = None,
    batch_size: int | None = None,
) -> ExtractOutput:
    """Extract fact tables from instance documents as Pandas dataframes.

    Args:
        instance_path: where to find instance documents.
        taxonomy_path: either a URL for a taxonomy, or the path to a ZIP
            archive that contains taxonomy files.
        form_number: the FERC form number (1, 2, 6, 60, 714).
        db_uri: the location of the database we are writing this form out to.
        archive_path: if taxonomy_path is a ZIP archive, this is a Path to the
            relevant taxonomy file within the archive. Otherwise, this should
            be None.
        datapackage_path: where to write a Frictionless datapackage descriptor
            to, if at all. Defaults to None, i.e., do not write one.
        metadata_path: where to write XBRL metadata to, if at all. Defaults
            to None, i.e., do not write one.
        requested_tables: only attempt to ingest data for these tables.
        workers: max number of workers to use.
        batch_size: max number of instances to parse for each worker.
    """
    logger = get_logger(__name__)
    table_defs = get_fact_tables(
        taxonomy_path=taxonomy_path,
        form_number=form_number,
        db_uri=db_uri,
        archive_path=archive_path,
        datapackage_path=datapackage_path,
        metadata_path=metadata_path,
    )

    instances = []
    for instance_builder in get_instances(Path(instance_path)):
        try:
            instances.append(instance_builder.parse())
        except XMLSyntaxError:
            logger.info(f"XBRL filing {instance_builder.name} is empty. Skipping.")
            continue

    table_data, stats = table_data_from_instances(
        instances,
        table_defs,
        requested_tables=requested_tables,
        workers=workers,
        batch_size=batch_size,
    )

    return ExtractOutput(
        table_defs=table_defs, instances=instances, table_data=table_data, stats=stats
    )


def table_data_from_instances(
    instances: list[Instance],
    table_defs: dict[str, FactTable],
    requested_tables: set[str] | None = None,
    batch_size: int | None = None,
    workers: int | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, list]]:
    """Turn FactTables into Dataframes by ingesting facts from instances.

    To handle lots of instances, we split the instances into batches.

    Args:
        instances: A list of Instance objects used for parsing XBRL filings.
        table_defs: the tables defined in the taxonomy s.t. we can try to match
            facts to them.
        archive_path: Path to taxonomy entry point within archive. If not None,
            then `taxonomy` should be a path to zipfile, not a URL.
        requested_tables: Optionally specify the set of tables to extract.
            If None, all possible tables will be extracted.
        batch_size: Number of filings to process before writing to DB.
        workers: Number of threads to create for parsing filings.
    """
    logger = get_logger(__name__)

    num_instances = len(instances)
    if not batch_size:
        batch_size = num_instances // workers if workers else num_instances

    num_batches = math.ceil(num_instances / batch_size)

    with Executor(max_workers=workers) as executor:
        # Bind arguments generic to all filings
        process_batches = partial(
            process_batch,
            table_defs=table_defs,
        )

        batched_instances = np.array_split(
            instances, math.ceil(num_instances / batch_size)
        )

        # Use thread pool to extract data from all filings in parallel
        results = {"dfs": defaultdict(list), "fact_ids": defaultdict(set)}
        for i, batch in enumerate(executor.map(process_batches, batched_instances)):
            logger.info(f"Finished batch {i + 1}/{num_batches}")
            for key, df in batch["dfs"].items():
                results["dfs"][key].append(df)
            for instance_name, fact_ids in batch["fact_ids"].items():
                results["fact_ids"][instance_name] |= fact_ids

        filings = {table: pd.concat(dfs) for table, dfs in results["dfs"].items()}
        metadata = {"fact_ids": results["fact_ids"]}

        return filings, metadata


def process_batch(
    instances: Iterable[Instance],
    table_defs: dict[str, FactTable],
) -> tuple[dict[str, pd.DataFrame], set[str]]:
    """Extract data from one batch of instances.

    Splitting instances into batches significantly improves multiprocessing
    performance. This is done explicitly rather than using ProcessPoolExecutor's
    chunk_size option so dataframes within the batch can be concatenated prior to
    returning to the parent process.

    Args:
        instances: Iterator of instances.
        table_defs: Dictionary mapping table names to FactTable objects describing table structure.
    """
    dfs: dict[str, pd.DataFrame] = {}
    fact_ids = {}
    for instance in instances:
        # Convert XBRL instance to dataframes. Log/skip if file is empty
        instance_dfs = process_instance(instance, table_defs)

        for key, df in instance_dfs.items():
            if key not in dfs:
                dfs[key] = []

            dfs[key].append(df)
        fact_ids[instance.filing_name] = instance.used_fact_ids

    dfs = {key: pd.concat(df_list) for key, df_list in dfs.items()}

    return {"dfs": dfs, "fact_ids": fact_ids}


def process_instance(
    instance: Instance,
    table_defs: dict[str, FactTable],
) -> dict[str, pd.DataFrame]:
    """Extract data from a single XBRL filing.

    This function will use the Instance object to parse
    a single XBRL filing. It then iterates through requested tables
    and populates them with data extracted from the filing.

    Args:
        instance: A single Instance object that represents an XBRL filing.
        table_defs: Dictionary mapping table names to FactTable objects describing table structure.
    """
    logger = get_logger(__name__)

    logger.info(f"Extracting {instance.filing_name}")

    dfs = {}
    for key, table_def in table_defs.items():
        dfs[key] = table_def.construct_dataframe(instance)

    return dfs


def get_fact_tables(
    taxonomy_path: str,
    form_number: int,
    db_uri: str,
    archive_path: str | None = None,
    filter_tables: set[str] | None = None,
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
        db_uri: URI of database used for constructing datapackage descriptor.
        archive_path: Path to taxonomy entry point within archive. If not None,
                then `taxonomy` should be a path to zipfile, not a URL.
        filter_tables: Optionally specify the set of tables to extract.
                If None, all possible tables will be extracted.
        datapackage_path: Create frictionless datapackage and write to specified path as JSON file.
                          If path is None no datapackage descriptor will be saved.
        metadata_path: Path to metadata json file to output taxonomy metadata.

    Returns:
        Dictionary mapping to table names to structure.
    """
    logger = get_logger(__name__)
    logger.info(f"Parsing taxonomy from {taxonomy_path}")
    taxonomy = Taxonomy.from_path(taxonomy_path, archive_path=archive_path)

    # Save taxonomy metadata
    taxonomy.save_metadata(metadata_path)

    datapackage = Datapackage.from_taxonomy(taxonomy, db_uri, form_number=form_number)

    if datapackage_path:
        # Verify that datapackage descriptor is valid before outputting
        frictionless_package = Package(descriptor=datapackage.dict(by_alias=True))
        if not frictionless_package.metadata_valid:
            raise RuntimeError("Generated datapackage is invalid")

        # Write to JSON file
        with open(datapackage_path, "w") as f:
            f.write(datapackage.json(by_alias=True))

    return datapackage.get_fact_tables(filter_tables=filter_tables)
