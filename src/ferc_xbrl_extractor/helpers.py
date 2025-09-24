"""Helper functions."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Helper function to append 'catalystcoop' to logger name and return logger."""
    return logging.getLogger(f"catalystcoop.{name}")
