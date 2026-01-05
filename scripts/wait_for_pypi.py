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
import sys
import time
import urllib.request
import ssl
import certifi

def check_pypi(package_name, version, repository_url):
    """Checks for the existence of a package version on a PyPI repository."""
    url = f"{repository_url}/{package_name}/"
    context = ssl.create_default_context(cafile=certifi.where())
    
    # Normalize version: PyPI often normalizes 1.1.3dev1 to 1.1.3.dev1
    normalized_version = version.replace("dev", ".dev").replace("rc", ".rc")

    print(f"Checking for {package_name}=={version} (or {normalized_version}) at {url}...")

    for i in range(60): # 60 * 5s = 300s = 5 minutes timeout
        try:
            with urllib.request.urlopen(url, context=context) as response:
                content = response.read()
                # Simple string check in the HTML/Simple API response
                if version.encode() in content or normalized_version.encode() in content:
                    print(f"Success: Version {version} found!")
                    return True
        except Exception as e:
            print(f"Error checking PyPI: {e}")
        
        print(f"Waiting... {i * 5}s/300s")
        time.sleep(5)
    
    return False

def main():
    parser = argparse.ArgumentParser(description="Wait for a package version to appear on PyPI/TestPyPI.")
    parser.add_argument("package_name", help="Name of the package (e.g. datacommons-mcp)")
    parser.add_argument("version", help="Version string to wait for")
    parser.add_argument("--repository", default="https://pypi.org/simple", help="PyPI repository URL (default: PyPI)")
    
    args = parser.parse_args()

    if check_pypi(args.package_name, args.version, args.repository):
        sys.exit(0)
    else:
        print(f"Timeout: Version {args.version} did not appear on {args.repository} within 5 minutes.")
        sys.exit(1)

if __name__ == "__main__":
    main()
