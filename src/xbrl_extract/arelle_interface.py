"""Abstract away interface to Arelle XBRL Library."""
from typing import List

from arelle import Cntlr, ModelManager, ModelXbrl
from arelle.ModelInstanceObject import ModelFact


def load_xbrl(path: str):
    """Load XBRL (either taxonomy or individual filing)."""
    cntlr = Cntlr.Cntlr()
    cntlr.startLogging(logFileName="logToPrint")
    model_manager = ModelManager.initialize(cntlr)
    return ModelXbrl.load(model_manager, path)


class InstanceFacts(object):
    """Container to manage access to facts from a single filing."""

    def __init__(self, instance_path: str):
        xbrl = load_xbrl(instance_path)
        self.fact_dict = {str(qname): fact for qname, fact in xbrl.factsByQname.items()}

    def _verify_dimensions(self, fact: ModelFact, axes: List[str]):
        for dim in fact.context.qnameDims.keys():
            if str(dim) not in axes:
                return False

        return True

    def __getitem__(self, key):
        return self.fact_dict[key]

    def get(self, key: str, axes: List[str]):
        """Get facts from fact dict that are in dimensions."""
        facts = self.fact_dict.get(key, [])

        return [fact for fact in facts if self._verify_dimensions(fact, axes)]
