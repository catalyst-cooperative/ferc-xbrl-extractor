import concurrent.futures
from unittest.mock import patch

from arelle import Cntlr

from ferc_xbrl_extractor.arelle_interface import load_taxonomy


def test_concurrent_taxonomy_load(tmp_path):
    cntlr = Cntlr.Cntlr()
    cntlr.webCache.cacheDir = str(tmp_path)
    cntlr.webCache.clear()
    path = "https://eCollection.ferc.gov/taxonomy/form60/2022-01-01/form/form60/form-60_2022-01-01.xsd"
    with patch("ferc_xbrl_extractor.arelle_interface.Cntlr.Cntlr", lambda: cntlr):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(load_taxonomy, path) for _ in range(2)]
        done, _not_done = concurrent.futures.wait(
            futures, timeout=10, return_when=concurrent.futures.ALL_COMPLETED
        )
    errored = {fut for fut in done if fut.exception()}
    assert len(errored) == 0
