# xbrl-extract
Utility for extracting data from XBRL filings into a SQLite database. The actual XBRL parsing is handled by [Arelle](https://arelle.org/arelle/), and tables generated from the structure of a specified taxonomy, and data contained in one or more filings.

To install using conda, run the following command, and activate the environment.

```
conda env create -f environment.yml
```



## CLI
A CLI is included in this repo for easily extracting data from XBRL filings. With the conda environment activated, you can use the following command:

```
xbrl_extract {taxonomy_path/url} {path_to_filings}
```
