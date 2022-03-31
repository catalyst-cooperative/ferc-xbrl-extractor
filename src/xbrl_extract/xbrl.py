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
    tables = FactTable.get_all_tables(taxonomy)
    dfs = {key: None for key in tables.keys()}
    for instance in instance_paths:
        print(instance)
        contexts, facts = parse(instance)
        for key, table in tables.items():
            df = table.to_dataframe(contexts, facts)
            if df is not None:
                dfs[key] = pd.concat(
                    [dfs[key], df],
                    ignore_index=True
                )

    for key, df in dfs.items():
        if df is not None:
            df.to_sql(key, engine, if_exists='append')


class FactTable(object):
    """Top level fact table."""

    def __init__(
        self,
        schedule: LinkRole,
    ):
        """Construct from an abstract and fact list."""
        self.name = schedule.definition
        self.axes: Dict[str, Axis] = {}
        self.table = None

        root_concept = schedule.concepts.child_concepts[0]
        for child_concept in root_concept.child_concepts:
            if child_concept.type == "Axis":
                self.axes[child_concept.name] = Axis(child_concept)
            elif child_concept.name.endswith("LineItems"):
                self.table = LineItems(child_concept)

        self.cols = self.initialize_dataframe()

    def to_dataframe(self, contexts, facts):
        """Convert fact table to dataframe."""
        if not self.table:
            return None

        df = pd.DataFrame(self.cols).set_index("context_id")

        axes = list(self.axes.keys())
        cols = list(self.cols.keys())

        contexts_in_table = [key for key, context in contexts.items()
                             if context.in_axes(axes)]

        for c_id in contexts_in_table:
            context_facts = facts[c_id]
            row = {}
            for fact in context_facts:
                if fact.name in cols:
                    row[fact.name] = fact.value

            if row:
                row.update(contexts[c_id].get_context_ids())
                df.loc[c_id] = row

        return df.sort_index()

    def initialize_dataframe(self):
        """Create dataframe based on types in table."""
        if not self.table:
            return None, None

        cols = {"context_id": np.array([], str),
                "entity_id": np.array([], str),
                "start_date": np.array([], str),
                "end_date": np.array([], str),
                "instant": np.array([], str)}

        for key, axis in self.axes.items():
            cols[key] = pd.Series([], dtype="string")

        cols.update(self.table.get_cols())

        return cols

    @staticmethod
    def get_all_tables(taxonomy: Taxonomy):
        return {role.definition: FactTable(role) for role in taxonomy.roles}


class Axis(object):
    """Defines a single axis with an a table."""

    def __init__(self, concept: Concept):
        """Axis concept."""
        self.name = concept.name
        self.domains = {}

        if len(concept.child_concepts) > 0:
            domain = concept.child_concepts[0]
            for member in domain.child_concepts:
                self.domains[member.name] = member.name


class LineItems(object):
    """List of line items."""

    def __init__(
        self,
        concept: Concept,
    ):
        """Create line items."""
        self.name = concept.name
        self.items = {child_concept.name: LineItem.from_concept(child_concept)
                      for child_concept in concept.child_concepts}

    def get_cols(self):
        """Get columns for dataframe."""
        cols = {}
        for item in self.items.values():
            cols.update(item.get_cols())

        return cols


class LineItem(object):
    """Abstract LineItem."""

    @staticmethod
    def from_concept(
        concept: Concept,
    ):
        """Check if table of facts or single fact."""
        if concept.name.endswith("Abstract"):
            return LineItems(concept)
        else:
            return Fact(concept)


class Fact(object):
    """Singular fact."""

    def __init__(
        self,
        concept: Concept,
    ):
        """Get all instances of fact."""
        self.name = concept.name
        self.dtype = DTYPE_MAP[concept.type] if concept.type in DTYPE_MAP \
            else DTYPE_MAP["Default"]

    def get_cols(self):
        """Get columns for dataframe."""
        return {self.name: np.array([], self.dtype)}
