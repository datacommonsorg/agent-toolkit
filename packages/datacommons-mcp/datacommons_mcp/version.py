"""
Version information for datacommons-mcp package.
"""

import logging
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("datacommons-mcp")
except PackageNotFoundError:
    logging.getLogger(__name__).warning("Could not determine package version")
    __version__ = "0.0.0+unknown"
