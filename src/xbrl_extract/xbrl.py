"""XBRL extractor."""
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from functools import cache, partial
import logging

import sqlalchemy as sa

from .taxonomy import Taxonomy, Concept, LinkRole
from .instance import parse


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
    gen_filing_id: bool = False,
    save_metadata: bool = False,
    verbose: bool = False,
    loglevel: bool = "WARNING"
):
    logger = logging.Logger(__name__)
    logger.setLevel(loglevel)

    if verbose:
        logger.addHandler(logging.StreamHandler())

    num_instances = len(instance_paths)
    if not batch_size:
        batch_size = num_instances

    with ThreadPoolExecutor(max_workers=threads) as executer:
        process_instances = partial(
            process_instance,
            engine=engine,
            logger=logger,
            save_metadata=save_metadata,
            gen_filing_id=gen_filing_id
        )

        results = executer.map(
            process_instances,
            instance_paths,
            chunksize=batch_size
        )

        current_batch = 1
        num_batches = num_instances // batch_size
        for i, dfs in enumerate(results):
            for key, df in dfs.items():
                if df is not None:
                    dfs[key] = pd.concat(
                        [dfs[key], df],
                        ignore_index=True
                    )

            # Write to disk after batch size to avoid using all memory
            if (i + 1) % batch_size == 0 or i == num_instances - 1:
                logger.info(f"Processed batch {current_batch}/{num_batches}")

                for key, df in dfs.items():
                    df.to_sql(key, engine, if_exists='append')
                    dfs[key] = None


def process_instance(
    instance: Tuple[str, int],
    engine: sa.engine.Engine,
    logger: logging.Logger,
    save_metadata: bool = False,
    gen_filing_id: bool = False
):
    instance_path, i = instance
    contexts, facts, tax_url = parse(instance_path)

    tables = get_fact_tables(tax_url, logger, save_metadata, gen_filing_id)
    filing_id = i if gen_filing_id else None

    logger.info(f"Extracting {instance_path}")

    dfs = {}
    for key, table in tables.items():
        dfs[key] = construct_dataframe(contexts, facts, table, filing_id)

    return dfs


@cache
def get_fact_tables(
    taxonomy_path: str,
    logger: logging.Logger,
    save_metadata: bool = False,
    gen_filing_id: bool = False,
):
    logger.info(f"Parsing taxonomy from {taxonomy_path}")
    taxonomy = Taxonomy.from_path(taxonomy_path, save_metadata)

    return {role.definition: get_fact_table(role, gen_filing_id)
            for role in taxonomy.roles}


def get_fact_table(schedule: LinkRole, gen_filing_id: bool = False):
    """Construct from an abstract and fact list."""
    root_concept = schedule.concepts.child_concepts[0]

    axes = [concept.name for concept in root_concept.child_concepts
            if concept.type == "Axis"]

    columns = {
        "context_id": str,
        "entity_id": str,
        "start_date": str,
        "end_date": str,
        "instant": np.bool8,
        **{axis: str for axis in axes}
    }

    if gen_filing_id:
        columns["filing_id"] = int

    for child_concept in root_concept.child_concepts:
        if child_concept.name.endswith("LineItems"):
            columns.update(get_columns_from_table(child_concept))

    return {"axes": axes, "columns": columns}


def construct_dataframe(contexts, facts, table_info, filing_id: int = None):
    """Convert fact table to dataframe."""
    cols = table_info['columns']
    axes = table_info['axes']

    contexts = {c_id: context for c_id, context in contexts.items()
                if context.in_axes(axes)}
    max_len = len(contexts)
    df = {key: [None]*max_len for key, dtype in cols.items()}

    for i, (c_id, context) in enumerate(contexts.items()):
        row = {fact.name: fact.value for fact in facts[c_id] if fact.name in cols}

        if row:
            row.update(contexts[c_id].get_context_ids(filing_id))

            for key, val in row.items():
                df[key][i] = val

    return pd.DataFrame(df).dropna(how='all').drop('context_id', axis=1)


def get_columns_from_table(concept: Concept):
    """Create line items."""
    cols = {}
    for item in concept.child_concepts:
        cols.update(get_cols_from_line_item(item))

    return cols


def get_cols_from_line_item(concept: Concept):
    """Check if table of facts or single fact."""
    if len(concept.child_concepts) > 0:
        return get_columns_from_table(concept)
    else:
        dtype = DTYPE_MAP[concept.type] if concept.type in DTYPE_MAP \
            else DTYPE_MAP["Default"]
        return {concept.name: dtype}
