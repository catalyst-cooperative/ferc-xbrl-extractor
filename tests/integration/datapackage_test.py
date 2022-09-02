"""Test datapackage descriptor from taxonomy."""
import pytest
from frictionless import Package

from ferc_xbrl_extractor.datapackage import Datapackage
from ferc_xbrl_extractor.taxonomy import Taxonomy


@pytest.mark.parametrize(
    "taxonomy_url",
    [
        "https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd"
    ],
)
def test_datapackage_generation(taxonomy_url):
    """Test that datapackage descriptor is valid."""
    taxonomy = Taxonomy.from_path(taxonomy_url)
    datapackage = Datapackage.from_taxonomy(taxonomy, "sqlite:///test_db.sqlite")
    assert Package(descriptor=datapackage.dict(by_alias=True)).metadata_valid
