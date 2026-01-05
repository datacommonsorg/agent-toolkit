"""
Version information for datacommons-mcp package.
"""

# Updating the version here will trigger a new version of datacommons-mcp
# package on PyPI when pushed to the main branch on github
# See .github/workflows/build-and-publish-datacommons-mcp.yaml
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("datacommons-mcp")
except PackageNotFoundError:
    # Package is not installed
    __version__ = "0.0.0+unknown"
