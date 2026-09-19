"""Extract data from XBRL filings."""

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

#: Compression codec used for all Parquet outputs written by this package.
PARQUET_COMPRESSION = "zstd"
#: Compression level used for all Parquet outputs written by this package.
PARQUET_COMPRESSION_LEVEL = 3
