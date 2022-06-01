"""Abstract away interface to Arelle XBRL Library."""
import json
from typing import Dict

from arelle import Cntlr, ModelManager, ModelXbrl, XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.ViewFileRelationshipSet import ViewRelationshipSet


def load_xbrl(path: str):
    """
    Load XBRL (either taxonomy or individual filing).

    Args:
        path: URL or local path pointing to an XBRL taxonomy or instance.
    """
    cntlr = Cntlr.Cntlr()
    cntlr.startLogging(logFileName="logToPrint")
    model_manager = ModelManager.initialize(cntlr)
    return ModelXbrl.load(model_manager, path)


def load_taxonomy(path: str):
    """
    Load XBRL taxonomy, and parse relationships.

    Args:
        path: URL or local path pointing to an XBRL taxonomy.
    """
    taxonomy = load_xbrl(path)

    # Interpret structure/relationships
    view = ViewRelationshipSet(taxonomy, "taxonomy.json", "roles", None, None, None)
    view.view(XbrlConst.parentChild, None, None, None)

    return taxonomy, view


def save_references(filename: str, concepts: Dict[str, ModelConcept]):
    """
    Save XBRL references to a JSON file.

    References are used in XBRL to provide additional metadata for Concepts.
    FERC provides references that identify the location of a concept in the
    raw form, which can be useful when linking data to historical data.

    Args:
        filename: File name to write references
        concepts: Dictionary mapping concept names to concepts
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
