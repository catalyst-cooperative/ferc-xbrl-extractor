"""XBRL extractor."""
import logging
from concurrent.futures import ProcessPoolExecutor as Executor
from functools import cache, partial
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import sqlalchemy as sa

from .instance import parse
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
    logger = logging.Logger(__name__)

    num_instances = len(instance_paths)
    if not batch_size:
        batch_size = num_instances

    with Executor(max_workers=threads) as executor:
        # Bind arguments generic to all filings
        process_instances = partial(
            process_instance,
            save_metadata=save_metadata,
        )

        # Use thread pool to extract data from all filings in parallel
        results = executor.map(process_instances, instance_paths, chunksize=batch_size)

        current_batch = 1
        num_batches = num_instances // batch_size

        # Concatenate dataframes extracted from each individual filing
        dfs = {}
        for i, instance_dfs in enumerate(results):
            for key, df in instance_dfs.items():
                if key not in dfs:
                    dfs[key] = []
                dfs[key].append(df)

            # Write to disk after batch size to avoid using all memory
            if (i + 1) % batch_size == 0 or i == num_instances - 1:  # noqa: FS001
                logger.info(f"Processed batch {current_batch}/{num_batches}")
                current_batch += 1

                for key, df_list in dfs.items():
                    logger.debug(f"Concatenating table - {key}")

                    df = pd.concat(df_list, ignore_index=True)
                    df.to_sql(key, engine, if_exists="append")
                    dfs[key] = []


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

    columns = {
        "context_id": str,
        "entity_id": str,
        "start_date": str,
        "end_date": str,
        "instant": np.bool8,
        "filing_name": str,
        **{axis: str for axis in axes},
    }

    for child_concept in root_concept.child_concepts:
        if child_concept.name.endswith("LineItems"):
            columns.update(get_columns_from_concept_tree(child_concept))

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
    columns = {}
    for item in concept.child_concepts:
        columns.update(get_column_from_concept(item))

    return columns


def get_column_from_concept(concept: Concept):
    """
    Check if concept is individual fact or has child facts.

    Check if concept contains child concepts, or is a lone fact. If concept is
    a fact, return a dictionary with the name and dtype, if it's a container
    treat it as the new root concept and get columns from sub-tree.

    Args:
        concept: Concept in question.

    Returns:
        Dictionary of columns for concept and child concepts.
    """
    if len(concept.child_concepts) > 0:
        return get_columns_from_concept_tree(concept)
    else:
        dtype = (
            DTYPE_MAP[concept.type]
            if concept.type in DTYPE_MAP
            else DTYPE_MAP["Default"]
        )
        return {concept.name: dtype}


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
    df = {key: [None] * max_len for key, dtype in columns.items()}

    # Loop through contexts and get facts in each context
    for i, (c_id, context) in enumerate(contexts.items()):
        row = {fact.name: fact.value for fact in facts[c_id] if fact.name in columns}

        if row:
            row.update(contexts[c_id].get_context_ids(filing_name))

            for key, val in row.items():
                df[key][i] = val

    return pd.DataFrame(df).dropna(how="all").drop("context_id", axis=1)
