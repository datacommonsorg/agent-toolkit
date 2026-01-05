"""
Version information for datacommons-mcp package.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("datacommons-mcp")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "0.0.0+unknown"
