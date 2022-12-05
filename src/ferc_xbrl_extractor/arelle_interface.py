"""Abstract away interface to Arelle XBRL Library."""
from typing import Literal

import pydantic
import stringcase
from arelle import Cntlr, FileSource, ModelManager, ModelXbrl, XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.ViewFileRelationshipSet import ViewRelationshipSet
from pydantic import BaseModel


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


class References(BaseModel):
    """Pydantic model that defines XBRL references.

    FERC uses XBRL references to link Concepts defined in its taxonomy to the physical
    paper form. These are included in the output metadata and can be useful for linking
    between XBRL and DBF data.

    This model is not a generic representation of XBRL references, but specific to those
    used by FERC.
    """

    account: str = pydantic.Field(None, alias="Account")
    form_location: list[dict[str, str]] = pydantic.Field([], alias="Form Location")


class Calculation(BaseModel):
    """Pydantic model that defines XBRL calculations.

    XBRL calculation relationships are also included in the metadata. Calculations are a
    validation tool used to define relationships between facts using some mathematical
    formula. For example, a calculation relationship might denote that one fact is equal
    to the sum of 2 or more other facts, and this relationship can be used to validate a
    filing.
    """

    name: str
    weight: float


class Metadata(BaseModel):
    """Pydantic model that defines metadata extracted from XBRL taxonomies.

    Taxonomies contain various metedata which are useful for interpreting XBRL filings.
    The metadata fields being extracted here include references, calculations, and balances.
    """

    name: str
    references: References
    calculations: list[Calculation]
    balance: Literal["credit", "debit"] | None

    @classmethod
    def from_concept(cls, concept: ModelConcept) -> "Metadata":
        """Get metadata for a single XBRL Concept.

        This function will create a Metadata object with metadata extracted for
        a single Concept.

        Args:
            concept: Concept to extract metadata from.
        """
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
                {
                    "name": stringcase.snakecase(calculation.toModelObject.name),
                    "weight": calculation.weight,
                }
            )

        concept_metadata["calculations"] = calculation_list
        concept_metadata["balance"] = concept.balance

        return cls(**concept_metadata)
