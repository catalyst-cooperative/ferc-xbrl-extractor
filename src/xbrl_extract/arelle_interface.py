"""Abstract away interface to Arelle XBRL Library."""
import json
from typing import Dict

from arelle import Cntlr, ModelManager, ModelXbrl, XbrlConst
from arelle.ModelDtsObject import ModelConcept


def load_xbrl(path: str):
    """Load XBRL (either taxonomy or individual filing)."""
    cntlr = Cntlr.Cntlr()
    cntlr.startLogging(logFileName="logToPrint")
    model_manager = ModelManager.initialize(cntlr)
    return ModelXbrl.load(model_manager, path)


def save_references(filename: str, concepts: Dict[str, ModelConcept]):
    """
    Save XBRL references to a JSON file.

    References are used in XBRL to provide additional metadata for Concepts.
    FERC provides references that identify the location of a concept in the
    raw form, which can be useful when linking data to historical data.
    """
    ref_dict = {}
    for name, concept in concepts.items():
        relationships = concept.modelXbrl.relationshipSet(
            XbrlConst.conceptReference
        ).fromModelObject(concept)

        relationship_dict = {}
        for relationship in relationships:
            relationship = relationship.toModelObject
            relationship_name = relationship.modelXbrl.roleTypeDefinition(
                relationship.role
            )
            part_dict = {
                part.localName: part.stringValue for part in relationship.iterchildren()
            }

            if relationship_name in relationship_dict:
                relationship_dict[relationship_name].append(part_dict)
            else:
                relationship_dict[relationship_name] = [part_dict]

        ref_dict[name] = relationship_dict

    with open(filename, "w") as f:
        json.dump(ref_dict, f)
