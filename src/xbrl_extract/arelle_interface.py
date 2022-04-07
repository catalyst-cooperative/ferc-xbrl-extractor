"""Abstract away interface to Arelle XBRL Library."""
from typing import Dict, List
import json

from arelle import Cntlr, ModelManager, ModelXbrl, XbrlConst
from arelle.ModelInstanceObject import ModelFact
from arelle.ModelDtsObject import ModelConcept


def load_xbrl(path: str):
    """Load XBRL (either taxonomy or individual filing)."""
    cntlr = Cntlr.Cntlr()
    cntlr.startLogging(logFileName="logToPrint")
    model_manager = ModelManager.initialize(cntlr)
    return ModelXbrl.load(model_manager, path)


def save_references(filename: str, concepts: Dict[str, ModelConcept]):
    ref_dict = {}
    for name, concept in concepts.items():
        relationships = concept.modelXbrl \
            .relationshipSet(XbrlConst.conceptReference) \
            .fromModelObject(concept)

        relationship_dict = {}
        for relationship in relationships:
            relationship = relationship.toModelObject
            relationship_name = relationship.modelXbrl.roleTypeDefinition(relationship.role)
            part_dict = {part.localName: part.stringValue
                         for part in relationship.iterchildren()}

            if relationship_name in relationship_dict:
                relationship_dict[relationship_name].append(part_dict)
            else:
                relationship_dict[relationship_name] = [part_dict]

        ref_dict[name] = relationship_dict

    with open(filename, 'w') as f:
        json.dump(ref_dict, f)


class InstanceFacts(object):
    """Container to manage access to facts from a single filing."""

    def __init__(self, instance_path: str):
        xbrl = load_xbrl(instance_path)
        self.fact_dict = {str(qname).split(':')[1]: fact
                          for qname, fact in xbrl.factsByQname.items()}

    def _verify_dimensions(self, fact: ModelFact, axes: List[str]):
        for dim in fact.context.qnameDims.keys():
            if str(dim).split(':')[1] not in axes:
                return False

        return True

    def __getitem__(self, key):
        return self.fact_dict[key]

    def get(self, key: str, axes: List[str]):
        """Get facts from fact dict that are in dimensions."""
        facts = self.fact_dict.get(key, [])

        return [fact for fact in facts if self._verify_dimensions(fact, axes)]
