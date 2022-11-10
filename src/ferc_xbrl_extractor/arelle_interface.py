"""Abstract away interface to Arelle XBRL Library."""
import json
from typing import TypedDict

import stringcase
from arelle import Cntlr, FileSource, ModelManager, ModelXbrl, XbrlConst
from arelle.ModelDtsObject import ModelConcept
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


class CalculationParameter(TypedDict):
    """Simple typed dictionary to wrap an XBRL calculation parameter.

    Calculations define mathematical relationships between facts. If a calculation
    relationship exists for a fact, it will provide a list of other facts that should
    equal the original fact when summed with optional scaling factors for each fact.
    For example, a calculation would look something like:

        fact1 = weight2*fact2 + weight3*fact3 + ....
    """

    name: str
    weight: int


def extract_metadata(filename: str, concepts: dict[str, ModelConcept]):
    """Extract metadata from XBRL taxonomies and write to JSON file.

    FERC uses XBRL references to link Concepts defined in its taxonomy to the physical
    paper form. These are included in the output metadata and can be useful for linking
    between XBRL and DBF data.

    XBRL calculation relationships are also included in the metadata. Calculations are a
    validation tool used to define relationships between facts using some mathematical
    formula. For example, a calculation relationship might denote that one fact is equal
    to the sum of 2 or more other facts, and this relationship can be used to validate a
    filing.

    Args:
        filename: File name to write references
        concepts: Dictionary mapping concept names to concepts
    """
    # Loop through all concepts in the taxonomy and extract metadata for each
    metadata = []
    for concept in concepts.values():
        # Get name and convert to snakecase to match output DB
        name = stringcase.snakecase(concept.name)
        concept_metadata = {"name": name}

        references = concept.modelXbrl.relationshipSet(
            XbrlConst.conceptReference
        ).fromModelObject(concept)

        # Loop through all references and add to metadata
        reference_dict = {}
        for reference in references:
            reference = reference.toModelObject
            reference_name = reference.modelXbrl.roleTypeDefinition(reference.role)
            # Several values can make up a single reference. Create a dictionary with these
            part_dict = {
                part.localName: part.stringValue for part in reference.iterchildren()
            }

            # There can also be several references with the same name, so store in list
            if reference_name in reference_dict:
                reference_dict[reference_name].append(part_dict)
            else:
                reference_dict[reference_name] = [part_dict]

            # Flatten out references where applicable
            if len(reference_dict[reference_name]) == 1 and len(part_dict) == 1:
                if reference_name in part_dict:
                    reference_dict[reference_name] = part_dict[reference_name]

        # Add references to metadata
        concept_metadata["references"] = reference_dict

        # Get calculations
        calculations = concept.modelXbrl.relationshipSet(
            XbrlConst.summationItem
        ).fromModelObject(concept)

        calculation_list = []
        for calculation in calculations:
            calculation_list.append(
                CalculationParameter(
                    name=stringcase.snakecase(calculation.toModelObject.name),
                    weight=calculation.weight,
                )
            )

        concept_metadata["calculations"] = calculation_list
        concept_metadata["balance"] = concept.balance

        if concept_metadata["references"] or concept_metadata["calculations"]:
            metadata.append(concept_metadata)

    with open(filename, "w") as f:
        json.dump(metadata, f, indent=4)
