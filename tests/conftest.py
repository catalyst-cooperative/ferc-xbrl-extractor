"""PyTest configuration module. Defines useful fixtures, command line args."""
import logging
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    """Add package-specific command line options to pytest.

    This is slightly magical -- pytest has a hook that will run this function
    automatically, adding any options defined here to the internal pytest options that
    already exist.
    """
    parser.addoption(
        "--sandbox",
        action="store_true",
        default=False,
        help="Flag to indicate that the tests should use a sandbox.",
    )

    parser.addoption(
        "--integration-data-dir",
        action="store",
        type=Path,
        default=Path(__file__).parent / "integration" / "data",
        help="Path to a data directory to use for integration testing. Useful "
        "for testing on larger samples of data than we ship in the repo.",
    )


@pytest.fixture(scope="session")
def test_dir():
    """Return the path to the top-level directory containing the tests.

    This might be useful if there's test data stored under the tests directory that
    you need to be able to access from elsewhere within the tests.

    Mostly this is meant as an example of a fixture.
    """
    return Path(__file__).parent


@pytest.fixture
def filing_data():
    """Test XBRL filing data."""
    return """<?xml version="1.0" encoding="UTF-8"?>
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ferc="http://ferc.gov/form/2022-01-01/ferc" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:utr="http://www.xbrl.org/2009/utr" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
          <link:schemaRef xlink:href="https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd" xlink:type="simple"/>
          <xbrli:context id="cid_1">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2021-01-01</xbrli:startDate>
              <xbrli:endDate>2021-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_2">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:instant>2021-12-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_3">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
              <xbrli:segment>
                <xbrldi:typedMember dimension="ferc:DimensionOneAxis">
                  <ferc:DimensionOne>Dim 1 Value</ferc:DimensionOne>
                </xbrldi:typedMember>
                <xbrldi:explicitMember dimension="ferc:DimensionTwoAxis">ferc:Dimension2Value</xbrldi:explicitMember>
              </xbrli:segment>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:instant>2021-12-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_4">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2020-01-01</xbrli:startDate>
              <xbrli:endDate>2020-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_5">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
              <xbrli:segment>
                <xbrldi:typedMember dimension="ferc:DimensionOneAxis">
                  <ferc:DimensionOne>Dim 1 Value</ferc:DimensionOne>
                </xbrldi:typedMember>
              </xbrli:segment>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2020-01-01</xbrli:startDate>
              <xbrli:endDate>2020-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <ferc:ReportDate id="fid_0" contextRef="cid_1">2021-04-18</ferc:ReportDate>
          <ferc:ColumnOne id="fid_1" contextRef="cid_1">value 1</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_2" contextRef="cid_1">value 2</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_3" contextRef="cid_4">value 3</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_4" contextRef="cid_4">value 4</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_5" contextRef="cid_2">value 5</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_6" contextRef="cid_2">value 6</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_7" contextRef="cid_3">value 7</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_8" contextRef="cid_3">value 8</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_9" contextRef="cid_5">value 9</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_10" contextRef="cid_5">value 10</ferc:ColumnTwo>
          <ferc:ColumnThree id="fid_11" contextRef="cid_2">value 11</ferc:ColumnThree>
          <ferc:ColumnFour id="fid_12" contextRef="cid_2">value 12</ferc:ColumnFour>
        </xbrli:xbrl>
    """


@pytest.fixture
def in_memory_filing(filing_data):
    """Create in memory file of filing data."""
    return BytesIO(filing_data.encode())


@pytest.fixture
def temp_file_filing(filing_data):
    """Create temporary file of filing data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = f"{tmpdir}/test.xbrl"
        with Path(file_path).open(mode="w") as f:
            f.write(filing_data)

        yield file_path


@pytest.fixture
def multi_filings():
    # CID 1, 4, 5 are duration; CID 2, 3 are instant.
    # columns 3,4 only appear in CID 2, i.e. instant.
    # FID 12 only appears in first filing, so when we dedupe we should see
    # FID 12 and FID 11_2

    files = [
        b"""<?xml version="1.0" encoding="UTF-8"?>
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ferc="http://ferc.gov/form/2022-01-01/ferc" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:utr="http://www.xbrl.org/2009/utr" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
          <link:schemaRef xlink:href="https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd" xlink:type="simple"/>
          <xbrli:context id="cid_1">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2021-01-01</xbrli:startDate>
              <xbrli:endDate>2021-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_2">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:instant>2021-12-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_3">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
              <xbrli:segment>
                <xbrldi:typedMember dimension="ferc:DimensionOneAxis">
                  <ferc:DimensionOne>Dim 1 Value</ferc:DimensionOne>
                </xbrldi:typedMember>
                <xbrldi:explicitMember dimension="ferc:DimensionTwoAxis">ferc:Dimension2Value</xbrldi:explicitMember>
              </xbrli:segment>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:instant>2021-12-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_4">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2020-01-01</xbrli:startDate>
              <xbrli:endDate>2020-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_5">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
              <xbrli:segment>
                <xbrldi:typedMember dimension="ferc:DimensionOneAxis">
                  <ferc:DimensionOne>Dim 1 Value</ferc:DimensionOne>
                </xbrldi:typedMember>
              </xbrli:segment>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2020-01-01</xbrli:startDate>
              <xbrli:endDate>2020-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <ferc:ReportDate id="fid_0" contextRef="cid_1">2021-04-18</ferc:ReportDate>
          <ferc:ColumnOne id="fid_1" contextRef="cid_1">value 1</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_2" contextRef="cid_1">value 2</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_3" contextRef="cid_4">value 3</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_4" contextRef="cid_4">value 4</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_5" contextRef="cid_2">value 5</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_6" contextRef="cid_2">value 6</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_7" contextRef="cid_3">value 7</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_8" contextRef="cid_3">value 8</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_9" contextRef="cid_5">value 9</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_10" contextRef="cid_5">value 10</ferc:ColumnTwo>
          <ferc:ColumnThree id="fid_11" contextRef="cid_2">value 11</ferc:ColumnThree>
          <ferc:ColumnFour id="fid_12" contextRef="cid_2">value 12</ferc:ColumnFour>
        </xbrli:xbrl>
        """,
        b"""<?xml version="1.0" encoding="UTF-8"?>
        <xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:ferc="http://ferc.gov/form/2022-01-01/ferc" xmlns:xbrldi="http://xbrl.org/2006/xbrldi" xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:utr="http://www.xbrl.org/2009/utr" xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xml="http://www.w3.org/XML/1998/namespace" xml:lang="en">
          <link:schemaRef xlink:href="https://eCollection.ferc.gov/taxonomy/form1/2022-01-01/form/form1/form-1_2022-01-01.xsd" xlink:type="simple"/>
          <xbrli:context id="cid_1_2">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2021-01-01</xbrli:startDate>
              <xbrli:endDate>2021-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_2_2">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:instant>2021-12-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_3_2">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
              <xbrli:segment>
                <xbrldi:typedMember dimension="ferc:DimensionOneAxis">
                  <ferc:DimensionOne>Dim 1 Value</ferc:DimensionOne>
                </xbrldi:typedMember>
                <xbrldi:explicitMember dimension="ferc:DimensionTwoAxis">ferc:Dimension2Value</xbrldi:explicitMember>
              </xbrli:segment>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:instant>2021-12-31</xbrli:instant>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_4_2">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2020-01-01</xbrli:startDate>
              <xbrli:endDate>2020-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <xbrli:context id="cid_5_2">
            <xbrli:entity>
              <xbrli:identifier scheme="http://www.ferc.gov/CID">EID1</xbrli:identifier>
              <xbrli:segment>
                <xbrldi:typedMember dimension="ferc:DimensionOneAxis">
                  <ferc:DimensionOne>Dim 1 Value</ferc:DimensionOne>
                </xbrldi:typedMember>
              </xbrli:segment>
            </xbrli:entity>
            <xbrli:period>
              <xbrli:startDate>2020-01-01</xbrli:startDate>
              <xbrli:endDate>2020-12-31</xbrli:endDate>
            </xbrli:period>
          </xbrli:context>
          <ferc:ReportDate id="fid_0_2" contextRef="cid_1_2">2021-04-19</ferc:ReportDate>
          <ferc:ColumnOne id="fid_1_2" contextRef="cid_1_2">value 1.1</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_2_2" contextRef="cid_1_2">value 2.1</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_3_2" contextRef="cid_4_2">value 3.1</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_4_2" contextRef="cid_4_2">value 4.1</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_5_2" contextRef="cid_2_2">value 5.1</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_6_2" contextRef="cid_2_2">value 6.1</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_7_2" contextRef="cid_3_2">value 7.1</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_8_2" contextRef="cid_3_2">value 8.1</ferc:ColumnTwo>
          <ferc:ColumnOne id="fid_9_2" contextRef="cid_5_2">value 9.1</ferc:ColumnOne>
          <ferc:ColumnTwo id="fid_10_2" contextRef="cid_5_2">value 10.1</ferc:ColumnTwo>
          <ferc:ColumnThree id="fid_11_2" contextRef="cid_2_2">value 11.1</ferc:ColumnThree>
        </xbrli:xbrl>
        """,
    ]
    return [BytesIO(f) for f in files]
