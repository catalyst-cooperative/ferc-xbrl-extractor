"""XBRL extractor."""
from typing import Dict, Callable, List, Iterable
import pandas as pd
import numpy as np

import sqlalchemy as sa

from arelle.ModelInstanceObject import ModelFact
from lxml import etree

from .taxonomy import Taxonomy, Concept, LinkRole
from .arelle_interface import InstanceFacts


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


def _get_entity_id(
    facts: InstanceFacts,
    entity_id_fact=None,
    entity_id=None,
):
    if entity_id_fact:
        # Assume there should only be one fact containing entity id
        return facts[entity_id_fact].pop().value
    elif entity_id:
        return entity_id
    else:
        return 0


def extract(
    taxonomy: Taxonomy,
    instance_paths: Iterable[str],
    engine: sa.engine.Engine,
    entity_id_fact=None,
    entity_id=None
):
    tables = FactTable.get_all_tables(taxonomy)
    dfs = {key: None for key in tables.keys()}
    for instance in instance_paths:
        facts = InstanceFacts(instance)
        entity_id = _get_entity_id(facts, entity_id_fact, entity_id)
        for key, table in tables.items():
            dfs[key] = table.to_dataframe(facts, entity_id, dfs[key])

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
                self.table = LineItems(
                    child_concept,
                    list(self.axes.keys()))

        self.cols, self.indices = self.initialize_dataframe()

    def to_dataframe(self, facts: InstanceFacts, entity_id, df=None):
        """Convert fact table to dataframe."""
        if not self.table:
            return None

        if df is None:
            df = pd.DataFrame(self.cols).set_index(list(self.indices))

        indices = self.indices
        indices["entity_id"] = entity_id

        for key, values in self.table.get_values(facts).items():
            indices.update({key: '' for key in indices.keys()
                            if key != "entity_id"})
            for value in values:
                indices["start_date"] = value.start_date
                indices["end_date"] = value.end_date
                indices["instant"] = value.instant
                for axis, val in value.dims.items():
                    indices[axis] = self.axes[axis].get_value(val)

                df.loc[tuple(indices.values()), key] = value.value

        return df.sort_index()

    def initialize_dataframe(self):
        """Create dataframe based on types in table."""
        if not self.table:
            return None, None

        cols = {"entity_id": np.array([]),
                "start_date": np.array([], str),
                "end_date": np.array([], str),
                "instant": np.array([], np.bool8)}

        for key, axis in self.axes.items():
            cols[key] = pd.Series([], dtype="string")

        cols.update(self.table.get_cols())

        indices = {
            "entity_id": None,
            "start_date": None,
            "end_date": None,
            "instant": None
        }

        indices.update({axis: None for axis in self.axes.keys()})

        return cols, indices

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

    def get_value(self, key: str):
        """Get the value associated with the axis."""
        if key not in self.domains:
            # Check if key is inline xml
            try:
                # TODO: This is removing the ferc prefix before parsing
                # This should be made more general
                element = etree.fromstring(key.replace('ferc:', ''))
                return element.text
            except etree.XMLSyntaxError:
                return key

        return self.domains[key]


class LineItems(object):
    """List of line items."""

    def __init__(
        self,
        concept: Concept,
        axes: List[str]
    ):
        """Create line items."""
        self.name = concept.name
        self.items = {child_concept.name: LineItem.from_concept(child_concept, axes)
                      for child_concept in concept.child_concepts}

    def get_cols(self):
        """Get columns for dataframe."""
        cols = {}
        for item in self.items.values():
            cols.update(item.get_cols())

        return cols

    def get_values(self, facts: InstanceFacts):
        """Get all values."""
        vals = {}
        for item in self.items.values():
            vals.update(item.get_values(facts))

        return vals


class LineItem(object):
    """Abstract LineItem."""

    @staticmethod
    def from_concept(
        concept: Concept,
        axes: List[str]
    ):
        """Check if table of facts or single fact."""
        if concept.name.endswith("Abstract"):
            return LineItems(concept, axes)
        else:
            return Fact(concept, axes)


class Fact(object):
    """Singular fact."""

    def __init__(
        self,
        concept: Concept,
        axes: List[str]
    ):
        """Get all instances of fact."""
        self.name = concept.name
        self.dtype = DTYPE_MAP[concept.type] if concept.type in DTYPE_MAP \
            else DTYPE_MAP["Default"]
        self.axes = axes

    def get_cols(self):
        """Get columns for dataframe."""
        return {self.name: np.array([], self.dtype)}

    def get_values(self, facts: InstanceFacts):
        """Get all values."""
        return {
            self.name: [
                Value(fact, self.dtype) for fact in facts.get(self.name, self.axes)
            ]
        }


class Value(object):
    """Instance of fact."""

    def __init__(self, fact: ModelFact, dtype: Callable):
        """Extract relevant data."""
        # If value cannot be interpretated as expected dtype, use default
        try:
            self.value = dtype(fact.value) if fact.value else dtype()
        except ValueError:
            self.value = dtype()

        self.dims = {str(qname).split(':')[1]: dim.propertyView[1]
                     for qname, dim in fact.context.qnameDims.items()}

        if fact.context.isInstantPeriod:
            self.start_date = str(fact.context.instantDatetime)
            self.end_date = ''
            self.instant = True
        else:
            self.start_date = str(fact.context.startDatetime)
            self.end_date = str(fact.context.endDatetime)
            self.instant = False
