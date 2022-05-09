"""A command line interface (CLI) to archive data from an RSS feed."""
import argparse
import logging
import re
from pathlib import Path
from zipfile import ZipFile

import coloredlogs
import feedparser
import requests


def parse_main():
    """Process base commands from the CLI."""
    parser = argparse.ArgumentParser(description="Archive filings from RSS feed")
    parser.add_argument(
        "-r", "--rss-path", default="./rssfeed", help="Specify path to RSS feed"
    )
    parser.add_argument(
        "-o",
        "--outfile",
        default="./extracted_filings.zip",
        help="Path to archive to be created",
    )
    parser.add_argument(
        "-c",
        "--clobber",
        action="store_true",
        default=False,
        help="Clobber existing outputs if they exist",
    )
    parser.add_argument(
        "-s",
        "--start-year",
        default=None,
        type=int,
        help="Specify start year for filter",
    )
    parser.add_argument(
        "-e", "--end-year", default=None, type=int, help="Specify end year for filter"
    )
    parser.add_argument(
        "-y", "--year", default=None, type=int, help="Specify single year for filter"
    )
    parser.add_argument(
        "-a", "--all-years", default=None, help="Pull content from all years"
    )
    parser.add_argument(
        "-f", "--form-name", default="Form 1", help="Specify form name for filter"
    )
    parser.add_argument(
        "--loglevel",
        help="Set log level",
        default="INFO",
    )
    parser.add_argument("--logfile", help="Path to logfile", default=None)

    return parser.parse_args()


def archive_filings(
    feed_path: Path,
    archive_path: Path,
    form_name: str,
    start_year: int,
    end_year: int,
    clobber: bool,
):
    """Pull filings and archive in zipfile."""
    logger = logging.getLogger(__name__)
    rss_feed = feedparser.parse(feed_path)

    logger.info(f"Archiving filings in {archive_path}.")

    mode = "w" if clobber else "a"
    with ZipFile(archive_path, mode) as zipfile:
        # Actual link to XBRL filing is only available in inline html
        # This regex pattern will help extract the actual link
        xbrl_link_pat = re.compile('href="(.+\.(xml|xbrl))">')  # noqa: W605

        # Loop through entries and filter
        for entry in rss_feed.entries:
            year = int(entry["ferc_year"])
            if year < start_year or year > end_year:
                continue

            if entry["ferc_formname"] != form_name:
                continue

            # Get link then download filing
            link = xbrl_link_pat.search(entry["summary_detail"]["value"])
            filing = requests.get(link.group(1))

            # Create file name from filing metadata
            filer = entry["title"].replace(" ", "")
            year = entry["ferc_year"]
            period = entry["ferc_period"]
            fname = f"{filer}{year}{period}.xbrl"

            # Write to zipfile
            with zipfile.open(fname, "w") as f:
                logger.info(f"Writing {fname} to archive.")
                f.write(filing.text.encode("utf-8"))


def main():
    """CLI for archiving FERC XBRL filings from RSS feed."""
    args = parse_main()

    logger = logging.getLogger("xbrl_extract")
    logger.setLevel(args.loglevel)
    log_format = "%(asctime)s [%(levelname)8s] %(name)s:%(lineno)s %(message)s"
    coloredlogs.install(fmt=log_format, level=args.loglevel, logger=logger)

    if args.logfile:
        file_logger = logging.FileHandler(args.logfile)
        file_logger.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_logger)

    start_year = args.start_year
    end_year = args.end_year

    if args.year is not None:
        start_year = args.year
        end_year = args.year

    if not start_year or not end_year:
        args.all_years = True

    if args.all_years is not None:
        start_year = 0
        end_year = 3000

    archive_filings(
        args.rss_path, args.outfile, args.form_name, start_year, end_year, args.clobber
    )
