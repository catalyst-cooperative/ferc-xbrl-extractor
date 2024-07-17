"""XBRL extractor."""

import io
import json
import math
import re
import warnings
from collections import defaultdict, namedtuple
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor as Executor
from functools import partial
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
from frictionless import Package
from lxml.etree import XMLSyntaxError  # nosec: B410

from ferc_xbrl_extractor.datapackage import Datapackage, FactTable
from ferc_xbrl_extractor.helpers import get_logger
from ferc_xbrl_extractor.instance import Instance, InstanceBuilder, get_instances
from ferc_xbrl_extractor.taxonomy import Taxonomy, get_metadata_from_taxonomies

ExtractOutput = namedtuple("ExtractOutput", ["table_defs", "table_data", "stats"])


def extract(
    filings: list[Path] | list[io.BytesIO],
    taxonomy_source: Path | io.BytesIO,
    form_number: int,
    db_uri: str,
    datapackage_path: Path | None = None,
    metadata_path: Path | None = None,
    requested_tables: set[str] | None = None,
    instance_pattern: str = r"",
    workers: int | None = None,
    batch_size: int | None = None,
) -> ExtractOutput:
    """Extract fact tables from instance documents as Pandas dataframes.

    Args:
        filings: list of filings or zip files with filings.
        taxonomy_source: either a URL/path to taxonomy or in memory archive of
            taxonomy.
        form_number: the FERC form number (1, 2, 6, 60, 714).
        db_uri: the location of the database we are writing this form out to.
        datapackage_path: where to write a Frictionless datapackage descriptor
            to, if at all. Defaults to None, i.e., do not write one.
        metadata_path: where to write XBRL metadata to, if at all. Defaults
            to None, i.e., do not write one.
        requested_tables: only attempt to ingest data for these tables.
        instance_pattern: only ingest data for instances matching this regex.
            Defaults to empty string which matches all.
        workers: max number of workers to use.
        batch_size: max number of instances to parse for each worker.
    """
    table_defs = get_fact_tables(
        taxonomy_source=taxonomy_source,
        form_number=form_number,
        db_uri=db_uri,
        datapackage_path=datapackage_path,
        metadata_path=metadata_path,
        filter_tables=requested_tables,
    )

    instance_builders = [
        ib
        for filing_path in filings
        for ib in get_instances(filing_path)
        if re.search(instance_pattern, ib.name)
    ]

    table_data, stats = table_data_from_instances(
        instance_builders,
        table_defs,
        workers=workers,
        batch_size=batch_size,
    )

    return ExtractOutput(table_defs=table_defs, table_data=table_data, stats=stats)


def table_data_from_instances(
    instance_builders: list[InstanceBuilder],
    table_defs: dict[str, FactTable],
    batch_size: int | None = None,
    workers: int | None = None,
) -> tuple[dict[str, pd.DataFrame], dict[str, list]]:
    """Turn FactTables into Dataframes by ingesting facts from instances.

    To handle lots of instances, we split the instances into batches.

    Args:
        instances: A list of Instance objects used for parsing XBRL filings.
        table_defs: the tables defined in the taxonomy that we will match facts to.
        batch_size: Number of filings to process before writing to DB.
        workers: Number of threads to create for parsing filings.
    """
    logger = get_logger(__name__)

    num_instances = len(instance_builders)
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
            instance_builders, math.ceil(num_instances / batch_size)
        )

        # Use thread pool to extract data from all filings in parallel
        results = {"dfs": defaultdict(list), "metadata": defaultdict(dict)}
        for i, batch in enumerate(executor.map(process_batches, batched_instances)):
            logger.info(f"Finished batch {i + 1}/{num_batches}")
            for key, df in batch["dfs"].items():
                results["dfs"][key].append(df)
            for instance_name, fact_ids in batch["metadata"].items():
                results["metadata"][instance_name] |= fact_ids

        with warnings.catch_warnings():
            warnings.filterwarnings(
                action="ignore",
                category=FutureWarning,
                message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated",
            )
            filings = {table: pd.concat(dfs) for table, dfs in results["dfs"].items()}
        metadata = results["metadata"]
        return filings, metadata


def process_batch(
    instance_builders: Iterable[InstanceBuilder],
    table_defs: dict[str, FactTable],
) -> tuple[dict[str, pd.DataFrame], set[str]]:
    """Extract data from one batch of instances.

    Splitting instances into batches significantly improves multiprocessing
    performance. This is done explicitly rather than using ProcessPoolExecutor's
    chunk_size option so dataframes within the batch can be concatenated prior to
    returning to the parent process.

    Args:
        instance_builders: Iterator of instance builders which can be parsed into instances.
        table_defs: Dictionary mapping table names to FactTable objects describing table structure.
    """
    logger = get_logger(__name__)
    dfs: defaultdict[str, list[pd.DataFrame]] = defaultdict(list)
    metadata = {}
    for instance_builder in instance_builders:
        # Convert XBRL instance to dataframes. Log/skip if file is empty
        try:
            instance = instance_builder.parse()
        except XMLSyntaxError:
            logger.info(f"XBRL filing {instance_builder.name} is empty. Skipping.")
            continue
        instance_dfs = process_instance(instance, table_defs)

        for key, df in instance_dfs.items():
            dfs[key].append(df)
        metadata[instance.filing_name] = {
            "used_facts": instance.used_fact_ids,
            "total_facts": instance.total_facts,
        }

    with warnings.catch_warnings():
        warnings.filterwarnings(
            action="ignore",
            category=FutureWarning,
            message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.",
        )
        dfs = {key: pd.concat(df_list) for key, df_list in dfs.items()}

    return {"dfs": dfs, "metadata": metadata}


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
    taxonomy_source: Path | io.BytesIO,
    form_number: int,
    db_uri: str,
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
        taxonomy_source: Zipfile with archived taxonomies for form.
        form_number: FERC Form number (can be 1, 2, 6, 60, 714).
        db_uri: URI of database used for constructing datapackage descriptor.
        filter_tables: Optionally specify the set of tables to extract.
            If None, all possible tables will be extracted.
        datapackage_path: Create frictionless datapackage and write to specified path
            as JSON file. If path is None no datapackage descriptor will be saved.
        metadata_path: Path to metadata json file to output taxonomy metadata.

    Returns:
        Dictionary mapping to table names to structure.
    """
    taxonomies = {}
    fact_tables = {}
    metadata = {}
    with ZipFile(taxonomy_source, "r") as taxonomy_archive:
        for taxonomy_version in taxonomy_archive.namelist():
            logger = get_logger(__name__)
            logger.info(f"Parsing taxonomy from {taxonomy_version}")
            with taxonomy_archive.open(taxonomy_version, mode="r") as f:
                taxonomy_date = re.search(r"\d{4}-\d{2}-\d{2}", taxonomy_version).group(
                    0
                )

                taxonomy_entry_point = f"taxonomy/form{form_number}/{taxonomy_date}/form/form{form_number}/form-{form_number}_{taxonomy_date}.xsd"
                taxonomy = Taxonomy.from_source(f, entry_point=taxonomy_entry_point)
                taxonomies[taxonomy_version] = taxonomy

    datapackage = Datapackage.from_taxonomies(
        taxonomies, db_uri, form_number=form_number
    )

    if datapackage_path:
        # Verify that datapackage descriptor is valid before outputting
        report = Package.validate_descriptor(datapackage.model_dump(by_alias=True))

        if not report.valid:
            raise RuntimeError(f"Generated datapackage is invalid - {report.errors}")

        # Write to JSON file
        with Path(datapackage_path).open(mode="w") as f:
            f.write(datapackage.model_dump_json(by_alias=True, indent=2))

    fact_tables = datapackage.get_fact_tables(filter_tables=filter_tables)

    # Save taxonomy metadata
    metadata = get_metadata_from_taxonomies(taxonomies)

    if metadata_path is not None:
        # Write to JSON file
        with Path(metadata_path).open(mode="w") as f:
            json.dump(metadata, f, indent=4)

    return fact_tables
