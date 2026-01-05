#!/usr/bin/env python3

# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import json
import os
import re
import sys
import tomllib
import urllib.request

"""
Helper script to determine the next sequential version for 'dev' or 'rc' releases.
It queries TestPyPI to find existing versions and strictly increments the suffix number
(e.g., 1.1.3dev1 -> 1.1.3dev2) to ensure monotonic versioning for automated pipelines.

Usage: python3 scripts/get_next_version.py --type dev OR python3 scripts/get_next_version.py --type rc
"""

# Add package release path to find the local version
# Read version from pyproject.toml

pyproject_path = os.path.join(os.path.dirname(__file__), "../packages/datacommons-mcp/pyproject.toml")
try:
    with open(pyproject_path, "rb") as f:
        project_data = tomllib.load(f)
        local_version = project_data["project"]["version"]
except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError) as e:
    print(f"Error reading version from pyproject.toml: {e}")
    sys.exit(1)

PACKAGE_NAME = "datacommons-mcp"
TEST_PYPI_JSON_URL = f"https://test.pypi.org/pypi/{PACKAGE_NAME}/json"

def get_next_version(base_version: str, release_type: str = "rc") -> None:
    try:
        with urllib.request.urlopen(TEST_PYPI_JSON_URL) as response: # noqa: S310
            data = json.loads(response.read())
            releases = data.get("releases", {}).keys()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"{base_version}{release_type}1")
            return
        raise

    # Pattern matches either rcN or devN based on input
    pattern = re.compile(rf"^{re.escape(base_version)}[\.]?{release_type}(\d+)$")

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
