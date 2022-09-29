"""Abstract away interface to Arelle XBRL Library."""
from arelle import Cntlr, FileSource, ModelManager, ModelXbrl, XbrlConst
from arelle.ViewFileRelationshipSet import ViewRelationshipSet


def load_xbrl(path: str | FileSource.FileSource):
    """Load XBRL (either taxonomy or individual filing).

    Args:
        path: URL or local path pointing to an XBRL taxonomy or instance.
    """
    cntlr = Cntlr.Cntlr()
    cntlr.startLogging(logFileName="logToPrint")
    model_manager = ModelManager.initialize(cntlr)
    return ModelXbrl.load(model_manager, path)


def load_taxonomy(path: str | FileSource.FileSource):
    """Load XBRL taxonomy, and parse relationships.

    Args:
        path: URL or local path pointing to an XBRL taxonomy.
    """
    taxonomy = load_xbrl(path)

    # Interpret structure/relationships
    view = ViewRelationshipSet(taxonomy, "taxonomy.json", "roles", None, None, None)
    view.view(XbrlConst.parentChild, None, None, None)

    return taxonomy, view


def load_taxonomy_from_archive(filepath: str, archive_path: str):
    """Load an XBRL taxonomy from a zipfile archive.

    Args:
        filepath: Path to zipfile on disc.
        archive_path: Relative path to taxonomy entry point within archive.
    """
    # Create arelle FileSource object
    f = FileSource.openFileSource(archive_path, sourceZipStream=filepath)

    return load_taxonomy(f)
