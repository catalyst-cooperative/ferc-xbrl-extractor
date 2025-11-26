"""Helper functions."""

import logging

import pandas as pd


def parse_dates(date_str: str) -> pd.Timestamp:
    """Helper to normalize date strings/parse in a consistent way."""
    try:
        if "24:00:00" in date_str:
            return pd.to_datetime(
                date_str.replace("24:00:00", "00:00:00")
            ) + pd.Timedelta(days=1)
        return pd.to_datetime(date_str)
    except ValueError:
        return pd.NaT


def get_logger(name: str) -> logging.Logger:
    """Helper function to append 'catalystcoop' to logger name and return logger."""
    return logging.getLogger(f"catalystcoop.{name}")
