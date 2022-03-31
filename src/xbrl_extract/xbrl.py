"""XBRL extractor."""
from typing import Dict, Callable, List, Iterable
import pandas as pd
import numpy as np

import sqlalchemy as sa

from arelle.ModelInstanceObject import ModelFact
from lxml import etree

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
    taxonomy: Taxonomy,
    instance_paths: Iterable[str],
    engine: sa.engine.Engine,
):
    tables = {role.definition: get_fact_table(role) for role in taxonomy.roles}
    dfs = {key: None for key in tables.keys()}
    for instance in instance_paths:
        print(instance)
        contexts, facts = parse(instance)
        for key, table in tables.items():
            df = construct_dataframe(contexts, facts, table)
            if df is not None:
                dfs[key] = pd.concat(
                    [dfs[key], df],
                    ignore_index=True
                )

    for key, df in dfs.items():
        if df is not None:
            df.to_sql(key, engine, if_exists='append')


def get_fact_table(schedule: LinkRole):
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

    for child_concept in root_concept.child_concepts:
        if child_concept.name.endswith("LineItems"):
            columns.update(get_columns_from_table(child_concept))

    return {"axes": axes, "columns": columns}


def construct_dataframe(contexts, facts, table_info):
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
            row.update(contexts[c_id].get_context_ids())

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
    if concept.name.endswith("Abstract"):
        return get_columns_from_table(concept)
    else:
        dtype = DTYPE_MAP[concept.type] if concept.type in DTYPE_MAP \
            else DTYPE_MAP["Default"]
        return {concept.name: dtype}
