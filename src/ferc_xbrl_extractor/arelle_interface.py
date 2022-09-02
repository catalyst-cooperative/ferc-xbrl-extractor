"""Abstract away interface to Arelle XBRL Library."""
from arelle import Cntlr, ModelManager, ModelXbrl, XbrlConst
from arelle.ViewFileRelationshipSet import ViewRelationshipSet


def load_xbrl(path: str):
    """Load XBRL (either taxonomy or individual filing).

    Args:
        path: URL or local path pointing to an XBRL taxonomy or instance.
    """
    cntlr = Cntlr.Cntlr()
    cntlr.startLogging(logFileName="logToPrint")
    model_manager = ModelManager.initialize(cntlr)
    return ModelXbrl.load(model_manager, path)


def load_taxonomy(path: str):
    """Load XBRL taxonomy, and parse relationships.

    Args:
        path: URL or local path pointing to an XBRL taxonomy.
    """
    taxonomy = load_xbrl(path)

    # Interpret structure/relationships
    view = ViewRelationshipSet(taxonomy, "taxonomy.json", "roles", None, None, None)
    view.view(XbrlConst.parentChild, None, None, None)

    return taxonomy, view
