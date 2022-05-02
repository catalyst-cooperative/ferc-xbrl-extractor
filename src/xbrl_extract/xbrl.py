"""XBRL extractor."""
import logging
from concurrent.futures import ProcessPoolExecutor as Executor
from functools import cache, partial
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import sqlalchemy as sa

from .instance import XbrlDb, parse
from .taxonomy import Concept, LinkRole, Taxonomy

DTYPE_MAP = {
    "String": str,
    "Decimal": np.float64,
    "GYear": np.int64,
    "Power": np.float64,
    "Integer": np.int64,
    "Monetary": np.int64,
    "PerUnit": np.float64,
    "Energy": np.int64,
    "Date": str,
    "FormType": str,
    "ReportPeriod": str,
    "Default": str,
}


def extract(
    instance_paths: List[Tuple[str, int]],
    engine: sa.engine.Engine,
    batch_size: Optional[int] = None,
    threads: Optional[int] = None,
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
    num_instances = len(instance_paths)
    if not batch_size:
        batch_size = num_instances

    # Prepare helper class for managing writing to db
    db_manager = XbrlDb(engine, batch_size, num_instances)

    with Executor(max_workers=threads) as executor:
        # Bind arguments generic to all filings
        process_instances = partial(
            process_instance,
            save_metadata=save_metadata,
        )

        # Use thread pool to extract data from all filings in parallel
        results = executor.map(process_instances, instance_paths, chunksize=batch_size)

        for instance_dfs in results:
            db_manager.append_instance(instance_dfs)


def process_instance(
    instance: Tuple[str, int],
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
        dfs[key] = construct_dataframe(contexts, facts, table, filing_name)

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

    return {role.definition: get_fact_table(role) for role in taxonomy.roles}


def get_fact_table(schedule: LinkRole):
    """
    Extract fact table structure from LinkRole.

    Use relationships described in LinkRole to initialize the structure of the
    fact table. Returns a dictionary containing axes and columns. 'axes' is a list
    of column names that make up the various dimensions which identify the contexts
    in the table. 'columns' is a dictionary that maps column names to data types.

    Args:
        schedule: Top level table structure.

    Returns:
        Dictionary axes and columns.
    """
    root_concept = schedule.concepts.child_concepts[0]

    axes = [
        concept.name
        for concept in root_concept.child_concepts
        if concept.name.endswith("Axis")
    ]

    generic_columns = {
        "context_id": str,
        "entity_id": str,
        "filing_name": str,
        **{axis: str for axis in axes},
    }

    concept_columns = get_columns_from_concept_tree(root_concept)
    columns = {
        "duration": {
            **generic_columns,
            "start_date": str,
            "end_date": str,
            **concept_columns["duration"],
        },
        "instant": {**generic_columns, "date": str, **concept_columns["instant"]},
    }

    return {"axes": axes, "columns": columns}


def get_columns_from_concept_tree(concept: Concept):
    """
    Loop through concepts to get column names.

    Traverse through concept DAG and create a column for any concepts that do
    not have any child concepts. Concepts with no children represent individual
    facts, while those with children are containers with one or more facts.

    Args:
        concept: Top level concept.

    Returns:
        Dictionary of columns.
    """
    columns = {"duration": {}, "instant": {}}
    for item in concept.child_concepts:
        if item.name.endswith("Axis"):
            continue

        if len(item.child_concepts) > 0:
            return get_columns_from_concept_tree(item)
        else:
            dtype = (
                DTYPE_MAP[item.type]
                if concept.type in DTYPE_MAP
                else DTYPE_MAP["Default"]
            )
            columns[item.period_type][item.name] = dtype

    return columns


def construct_dataframe(contexts, facts, table_info, filing_name: str = None):
    """
    Populate table with relevant data from filing.

    Args:
        contexts (Dict): Dictionary containing all contexts in filing.
        facts (Dict): Dictionary containing all facts in filing.
        table_info (Dict): Dictionary containing columns and axes in table.
        filing_name: Unique filing id.
    """
    columns = table_info["columns"]
    axes = table_info["axes"]

    # Filter contexts to only those relevant to table
    contexts = {
        c_id: context
        for c_id, context in contexts.items()
        if context.check_dimensions(axes)
    }

    # Get the maximum number of rows that could be in table and allocate space
    max_len = len(contexts)

    # Split into two dataframes (one for instant period, one for duration)
    df_duration = {key: [None] * max_len for key, dtype in columns["duration"].items()}
    df_instant = {key: [None] * max_len for key, dtype in columns["instant"].items()}

    # Loop through contexts and get facts in each context
    for i, (c_id, context) in enumerate(contexts.items()):
        period_type = "instant" if context.period.instant else "duration"
        row = {
            fact.name: fact.value
            for fact in facts[c_id]
            if fact.name in columns[period_type]
        }

        if row:
            row.update(contexts[c_id].get_context_ids(filing_name))

            for key, val in row.items():
                if context.period.instant:
                    df_instant[key][i] = val
                else:
                    df_duration[key][i] = val

    return (
        pd.DataFrame(df_duration).dropna(how="all").drop("context_id", axis=1),
        pd.DataFrame(df_instant).dropna(how="all").drop("context_id", axis=1),
    )
