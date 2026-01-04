#!/usr/bin/env python3
import json
import urllib.request
import sys
import os
import re

import argparse

# Add package release path to find the local version
sys.path.append(os.path.join(os.path.dirname(__file__), '../packages/datacommons-mcp'))
try:
    from datacommons_mcp.version import __version__ as local_version
except ImportError:
    print("Error: Could not find datacommons_mcp.version")
    sys.exit(1)

PACKAGE_NAME = "datacommons-mcp"
TEST_PYPI_JSON_URL = f"https://test.pypi.org/pypi/{PACKAGE_NAME}/json"

def get_next_version(base_version, release_type="rc"):
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(TEST_PYPI_JSON_URL, context=ctx) as response:
            data = json.loads(response.read())
            releases = data.get("releases", {}).keys()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"{base_version}{release_type}1")
            return
        raise

    # Pattern matches either rcN or devN based on input
    pattern = re.compile(rf"^{re.escape(base_version)}{release_type}(\d+)$")
    
    max_ver = 0
    
    for release in releases:
        match = pattern.match(release)
        if match:
            ver_num = int(match.group(1))
            if ver_num > max_ver:
                max_ver = ver_num

    next_ver = max_ver + 1
    print(f"{base_version}{release_type}{next_ver}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get next release tag for datacommons-mcp")
    parser.add_argument("--type", choices=["rc", "dev"], default="rc", help="Release type: rc (default) or dev")
    args = parser.parse_args()

    get_next_version(local_version, args.type)
