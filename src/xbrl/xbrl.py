"""XBRL extractor."""
from typing import Dict, Set
import pandas as pd

from arelle import Cntlr, ModelManager, ModelXbrl
from arelle.ModelInstanceObject import ModelFact

from .xbrl_taxonomy import Taxonomy, Concept


def _get_fact_dict(instance_path: str):
    """Temporary function used for testing."""
    model_manager = ModelManager.initialize(Cntlr.Cntlr())
    xbrl = ModelXbrl.load(model_manager, instance_path)
    fd = {str(qname): fact for qname, fact in xbrl.factsByQname.items()}

    return fd


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
                self.table = LineItems(child_concept, _get_fact_dict(instance_path))

        if not self.table:
            raise TypeError("Error processing XBRL: No LineItems.")

        for axis_name, axis in self.axes.items():
            if not axis.intialized:
                axis_key = axis_name.rstrip("Axis")
                axis.process_values(self.table.items.pop(axis_key))

    def to_dataframe(self):
        """Convert fact table to dataframe."""
        pass

    def initialize_dataframe(self):
        """Initialize dataframe."""
        cols = {}

        for key, axis in self.axes:
            cols[key] = pd.Series([], dtype="string")


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

    def __init__(self, concept: Concept, fact_dict: Dict[str, Set[ModelFact]]):
        """Create line items."""
        self.name = concept.name
        self.items = {child_concept.name: LineItem.from_concept(child_concept, fact_dict)
                      for child_concept in concept.child_concepts}

    def get_cols(self):
        """Get columns for dataframe."""
        cols = {}
        for item in self.items:
            cols.update(item.get_cols())


class LineItem(object):
    """Abstract LineItem."""

    @staticmethod
    def from_concept(concept: Concept, fact_dict: Dict[str, Set[ModelFact]]):
        """Check if table of facts or single fact."""
        if concept.name.endswith("Abstract"):
            return Table(concept, fact_dict)
        else:
            return Fact(concept, fact_dict)


class Fact(object):
    """Singular fact."""

    def __init__(self, concept: Concept, fact_dict: Dict[str, Set[ModelFact]]):
        """Get all instances of fact."""
        self.name = concept.name
        if fact_dict.get(self.name):
            self.values = [Value(fact) for fact in fact_dict.get(self.name)]
        else:
            self.values = []

    def get_cols(self):
        """Get columns for dataframe."""
        pass


class Value(object):
    """Instance of fact."""

    def __init__(self, fact: ModelFact):
        """Extract relevant data."""
        self.value = fact.value
        self.dims = {str(qname): dim.propertyView[1]
                     for qname, dim in fact.context.qnameDims.items()}
        if fact.context.isInstantPeriod:
            self.start_date = fact.context.instantDatetime
            self.end_date = None
        else:
            self.start_date = fact.context.startDatetime
            self.end_date = fact.context.endDatetime


class Table(object):
    """Table of facts."""

    def __init__(self, concept: Concept, fact_dict: Dict[str, Set[ModelFact]]):
        """Get facts."""
        self.name = concept.name
        self.child_items = [LineItem.from_concept(child_concept, fact_dict)
                            for child_concept in concept.child_concepts]
