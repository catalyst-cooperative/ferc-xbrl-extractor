"""XBRL extractor."""
from typing import Dict, Set, Callable, List
import pandas as pd
import numpy as np

from arelle import Cntlr, ModelManager, ModelXbrl
from arelle.ModelInstanceObject import ModelFact

from .xbrl_taxonomy import Taxonomy, Concept


DTYPE_MAP = {
    "String": str,
    "Decimal": np.float64,
    "GYear": np.int64,
    "Power": np.float64,
    "Integer": np.int64,
    "Monetary": np.int64,
    "PerUnit": np.float64,
    "Energy": np.int64,
}


def temp_get_table():
    xbrl_tax_path: str = "https://eCollection.ferc.gov/taxonomy/form1/" \
                         "2022-01-01/form/form1/form-1_2022-01-01.xsd"
    tax = Taxonomy.from_path(xbrl_tax_path)
    instance_path = "/home/zach/catalyst/xbrl/2011/2011/VirginiaElectricAndPowerCompany-186-2011Q4F1.xbrl"

    return FactTable(tax.get_page(402)[1].concepts.child_concepts[0], instance_path)


def _get_fact_dict(instance_path: str):
    """Temporary function used for testing."""
    model_manager = ModelManager.initialize(Cntlr.Cntlr())
    xbrl = ModelXbrl.load(model_manager, instance_path)
    fd = {str(qname): fact for qname, fact in xbrl.factsByQname.items()}

    return fd


def _verify_dimensions(fact: ModelFact, axes: List[str]):
    for dim in fact.context.qnameDims.keys():
        if str(dim) not in axes:
            return False

    return True


def _get_facts(key: str, fact_dict: Dict[str, Set[ModelFact]], axes: List[str]):
    """Get facts from fact dict that are in dimensions."""
    facts = fact_dict.get(key)

    facts = [fact for fact in facts if _verify_dimensions(fact, axes)]

    return facts


class FactTable(object):
    """Top level fact table."""

    def __init__(self, root_concept: Concept, instance_path: str):
        """Construct from an abstract and fact list."""
        self.name = root_concept.name

        self.axes: Dict[str, Axis] = {}
        self.table = None
        for child_concept in root_concept.child_concepts:
            if child_concept.type == "Axis":
                self.axes[child_concept.name] = Axis(child_concept)
            elif child_concept.name.endswith("LineItems"):
                self.table = LineItems(child_concept,
                                       _get_fact_dict(instance_path),
                                       list(self.axes.keys()))

        if not self.table:
            raise TypeError("Error processing XBRL: No LineItems.")

        for axis_name, axis in self.axes.items():
            if not axis.intialized:
                axis_key = axis_name.rstrip("Axis")
                axis.process_values(self.table.items.pop(axis_key))

    def to_dataframe(self):
        """Convert fact table to dataframe."""
        df, indices = self.initialize_dataframe()

        for key, values in self.table.get_values().items():
            indices = {key: '' for key in indices.keys()}
            for value in values:
                indices["start_date"] = value.start_date
                indices["end_date"] = value.start_date
                for axis, val in value.dims.items():
                    indices[axis] = self.axes[axis].allowable[val]

                df.loc[tuple(indices.values()), key] = value.value

        return df

    def initialize_dataframe(self):
        """Initialize dataframe."""
        cols = {"start_date": np.array([], np.datetime64),
                "end_date": np.array([], np.datetime64)}

        for key, axis in self.axes.items():
            cols[key] = pd.Series([], dtype="string")

        cols.update(self.table.get_cols())

        df = pd.DataFrame(cols)

        indices = {"start_date": None, "end_date": None}
        indices.update({axis: None for axis in self.axes.keys()})

        return df.set_index(list(indices.keys())), indices


class Axis(object):
    """Defines a single axis with an a table."""

    def __init__(self, concept: Concept):
        """Axis concept."""
        self.name = concept.name
        self.allowable = {}
        self.intialized = False

        if len(concept.child_concepts) > 0:
            self.intialized = True
            domain = concept.child_concepts[0]
            for member in domain.child_concepts:
                self.allowable[member.name] = member.name

    def process_values(self, fact: 'Fact'):
        """Process values contained in axis."""
        self.allowable = {val.dims[self.name]: val.value for val in fact.values
                          if val.dims.get(self.name)}
        self.intialized = True


class LineItems(object):
    """List of line items."""

    def __init__(
        self,
        concept: Concept,
        fact_dict: Dict[str, Set[ModelFact]],
        axes: List[str]
    ):
        """Create line items."""
        self.name = concept.name
        self.items = {child_concept.name: LineItem.from_concept(child_concept, fact_dict, axes)
                      for child_concept in concept.child_concepts}

    def get_cols(self):
        """Get columns for dataframe."""
        cols = {}
        for item in self.items.values():
            cols.update(item.get_cols())

        return cols

    def get_values(self):
        """Get all values."""
        vals = {}
        for item in self.items.values():
            vals.update(item.get_values())

        return vals


class LineItem(object):
    """Abstract LineItem."""

    @staticmethod
    def from_concept(
        concept: Concept,
        fact_dict: Dict[str, Set[ModelFact]],
        axes: List[str]
    ):
        """Check if table of facts or single fact."""
        if concept.name.endswith("Abstract"):
            return LineItems(concept, fact_dict, axes)
        else:
            return Fact(concept, fact_dict, axes)


class Fact(object):
    """Singular fact."""

    def __init__(
        self,
        concept: Concept,
        fact_dict: Dict[str, Set[ModelFact]],
        axes: List[str]
    ):
        """Get all instances of fact."""
        self.name = concept.name
        print(concept.type)
        self.dtype = DTYPE_MAP[concept.type]
        if fact_dict.get(self.name):
            self.values = [Value(fact, self.dtype)
                           for fact in _get_facts(self.name, fact_dict, axes)]
        else:
            self.values = []

    def get_cols(self):
        """Get columns for dataframe."""
        return {self.name: np.array([], self.dtype)}

    def get_values(self):
        """Get all values."""
        return {self.name: self.values}


class Value(object):
    """Instance of fact."""

    def __init__(self, fact: ModelFact, dtype: Callable):
        """Extract relevant data."""
        self.value = dtype(fact.value)
        self.dims = {str(qname): dim.propertyView[1]
                     for qname, dim in fact.context.qnameDims.items()}
        if fact.context.isInstantPeriod:
            self.start_date = fact.context.instantDatetime.timestamp()
            self.end_date = 0
        else:
            self.start_date = fact.context.startDatetime.timestamp()
            self.end_date = fact.context.endDatetime.timestamp()
