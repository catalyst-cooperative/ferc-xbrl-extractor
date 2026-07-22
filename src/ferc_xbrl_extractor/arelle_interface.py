"""Abstract away interface to Arelle XBRL Library."""

import time
from pathlib import Path
from typing import BinaryIO, Literal, cast

import pydantic
import stringcase
from arelle import Cntlr, FileSource, ModelManager, ModelXbrl, XbrlConst
from arelle.ModelDtsObject import ModelConcept
from arelle.ModelObject import ModelObject
from arelle.ViewFileRelationshipSet import ViewRelationshipSet
from pydantic import BaseModel


def _taxonomy_view(
    taxonomy_source: str | FileSource.FileSource, max_retries: int = 7
) -> tuple[ModelXbrl.ModelXbrl, ViewRelationshipSet]:
    """Use Arelle to load a taxonomy and build its parent-child relationship view.

    As it parses a taxonomy, Arelle downloads the schema/linkbase files it
    references to a local on-disk cache (managed by Arelle's own ``webCache``),
    then reads them back from there. When two or more callers load the *same*
    taxonomy concurrently -- e.g. multiple threads or processes each extracting
    a different filing that shares one taxonomy version -- their cache writes
    can race, and Arelle raises ``FileExistsError`` when one caller tries to
    create a cache file another is already writing.

    This is a transient condition, not a real failure: by the time we retry,
    the other caller has usually finished writing the file, so the retried
    ``ModelXbrl.load`` call reads the now-complete cache entry instead of
    trying to write it again. The loop therefore retries *only*
    ``FileExistsError``, with exponential backoff, up to ``max_retries``
    attempts before giving up and re-raising. Any other exception (a genuinely
    missing taxonomy, malformed XBRL, an unrelated network error, ...) is
    allowed to propagate immediately on the first attempt, since retrying
    those wouldn't help -- they aren't the race this loop exists to work
    around. See ``test_concurrent_taxonomy_load`` (integration) and
    ``test_taxonomy_view_retries_then_raises_after_max_retries`` (unit) for
    coverage of this behavior.

    Args:
        taxonomy_source: URL, local path, or in-memory ``FileSource`` pointing
            at the taxonomy entry point.
        max_retries: Maximum number of load attempts before giving up and
            re-raising the last ``FileExistsError``.
    """
    cntlr = Cntlr.Cntlr()
    cntlr.startLogging(logFileName="logToPrint")
    # Arelle types `logger` as `Logger | None` since it's unset until `startLogging()`
    # runs -- which we just did, so it's populated from here on.
    assert cntlr.logger is not None
    model_manager = ModelManager.initialize(cntlr)
    for try_count in range(max_retries):
        try:
            cntlr.logger.debug(f"Try #{try_count}: {taxonomy_source=}")
            taxonomy = ModelXbrl.load(model_manager, taxonomy_source)
            break
        except FileExistsError as e:
            if (try_count + 1) == max_retries:
                raise e
            backoff = 2 ** (try_count + 1)
            cntlr.logger.warning(f"Failed try #{try_count}, retrying in {backoff}s")
            time.sleep(backoff)

    view = ViewRelationshipSet(taxonomy, "taxonomy.json", "roles", None, None, None)
    view.view(XbrlConst.parentChild, None, None, None)

    return taxonomy, view


def load_taxonomy(
    path: str | Path,
) -> tuple[ModelXbrl.ModelXbrl, ViewRelationshipSet]:
    """Load XBRL taxonomy, and parse relationships.

    Args:
        path: URL or local path pointing to an XBRL taxonomy.
    """
    # arelle only works with `str`, not `Path` - as of version 2.12.2
    source = str(path)
    return _taxonomy_view(source)


def load_taxonomy_from_archive(
    taxonomy_archive: BinaryIO, entry_point: str | Path
) -> tuple[ModelXbrl.ModelXbrl, ViewRelationshipSet]:
    """Load an XBRL taxonomy from a zipfile archive.

    Args:
        taxonomy_archive: In memory taxonomy archive.
        entry_point: Relative path to taxonomy entry point within archive.
    """
    file_source = FileSource.openFileSource(
        str(entry_point), sourceZipStream=taxonomy_archive
    )
    return _taxonomy_view(file_source)


class References(BaseModel):
    """Pydantic model that defines XBRL references.

    FERC uses XBRL references to link Concepts defined in its taxonomy to the physical
    paper form. These are included in the output metadata and can be useful for linking
    between XBRL and DBF data.

    This model is not a generic representation of XBRL references, but specific to those
    used by FERC.
    """

    account: str | None = pydantic.Field(None, alias="Account")
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

    Taxonomies contain various metadata which are useful for interpreting XBRL filings.
    The metadata fields being extracted here include references, calculations, and balances.
    """

    name: str
    references: References
    calculations: list[Calculation]
    balance: Literal["credit", "debit"] | None = None

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

        # A loaded Concept always belongs to a ModelXbrl -- only unset on freestanding
        # prototype objects, which don't reach this code path.
        assert concept.modelXbrl is not None
        references = concept.modelXbrl.relationshipSet(
            XbrlConst.conceptReference
        ).fromModelObject(concept)

        # Loop through all references and add to metadata
        reference_dict = {}
        for reference in references:
            reference = reference.toModelObject
            assert reference is not None
            assert reference.modelXbrl is not None
            reference_name = reference.modelXbrl.roleTypeDefinition(reference.role)
            # Several values can make up a single reference. Create a dictionary with these.
            # iterchildren() is inherited from lxml's generic `_Element`, but Arelle
            # registers its own element class, so children are actually `ModelObject`s
            # with `localName`/`stringValue` attributes lxml's stubs don't know about.
            part_dict = {
                cast(ModelObject, part).localName: cast(ModelObject, part).stringValue
                for part in reference.iterchildren()
            }

            # There can also be several references with the same name, so store in list
            if reference_name in reference_dict:
                existing_entry = reference_dict[reference_name]
                # `reference_dict[reference_name]` can be flattened to a bare `str`
                # below (see comment) the *first* time a reference_name occurs with a
                # single, name-matching part. If that same reference_name recurs after
                # being flattened, this logic can't represent both shapes at once --
                # turn what would otherwise be a cryptic `AttributeError` into a
                # legible one so this gets noticed and investigated if it ever
                # actually happens with real FERC filing data.
                assert isinstance(existing_entry, list), (
                    f"Reference {reference_name!r} was flattened to a single value for "
                    "an earlier reference on this concept, but recurred here -- the "
                    "flattening logic below can't represent both shapes."
                )
                existing_entry.append(part_dict)
            else:
                reference_dict[reference_name] = [part_dict]

            # Flatten out references where applicable
            if (
                len(reference_dict[reference_name]) == 1
                and len(part_dict) == 1
                and reference_name in part_dict
            ):
                reference_dict[reference_name] = part_dict[reference_name]

        # Add references to metadata
        concept_metadata["references"] = reference_dict

        # Get calculations
        calculations = concept.modelXbrl.relationshipSet(
            XbrlConst.summationItem
        ).fromModelObject(concept)

        calculation_list = []
        for calculation in calculations:
            assert calculation.toModelObject is not None
            # summation-item relationships always link concept to concept, but
            # `toModelObject` is typed as the generic `ModelObject` base class, which
            # doesn't declare `.name` -- only its `ModelConcept` subclass does.
            calc_concept = cast(ModelConcept, calculation.toModelObject)
            calculation_list.append(
                {
                    "name": stringcase.snakecase(calc_concept.name),
                    "weight": calculation.weight,
                }
            )

        concept_metadata["calculations"] = calculation_list
        concept_metadata["balance"] = concept.balance

        # Arelle types `balance` as a plain `str`, wider than our `Literal["credit",
        # "debit"] | None` -- pydantic validates the actual value at construction time.
        return cls(**concept_metadata)  # ty:ignore[invalid-argument-type]
