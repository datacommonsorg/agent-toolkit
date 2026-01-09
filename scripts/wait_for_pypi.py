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

"""
Wait for a package version to appear on PyPI/TestPyPI.

Usage:
    python wait_for_pypi.py <package_name> <version> [--repository <repository_url>]
"""

import argparse
import subprocess
import sys
import time


def check_pypi(package_name: str, version: str, repository_url: str) -> bool:
    """Checks for the existence of a package version using pip."""
    if "test.pypi.org" in repository_url:
        # If checking TestPyPI, we need to handle dependencies that might be on main PyPI
        # But for existence check, we can just say --no-deps
        pass

    print(
        f"Verifying downloadability of {package_name}=={version} from {repository_url}..."
    )

    import tempfile

    for i in range(60):  # 5 minutes
        try:
            # Use pip download --no-deps to verify the file is actually resolvable
            # We use --no-cache-dir to avoid false positives from local cache
            with tempfile.TemporaryDirectory() as temp_dir:
                cmd = [
                    sys.executable,
                    "-m",
                    "pip",
                    "download",
                    f"{package_name}=={version}",
                    "--no-deps",
                    "--no-cache-dir",
                    "--index-url",
                    repository_url,
                    "--dest",
                    temp_dir,  # Download to tmp to verify file retrieval
                ]

                result = subprocess.run(  # noqa: S603
                    cmd, check=False, capture_output=True, text=True
                )

                if result.returncode == 0:
                    print(
                        f"Success: pip successfully located and downloaded {package_name}=={version}!"
                    )
                    return True

        except Exception as e:
            print(f"Error checking PyPI: {e}")

        print(f"Waiting... {i * 5}s/300s")
        time.sleep(5)

    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wait for a package version to appear on PyPI/TestPyPI."
    )
    parser.add_argument(
        "package_name", help="Name of the package (e.g. datacommons-mcp)"
    )
    parser.add_argument("version", help="Version string to wait for")
    parser.add_argument(
        "--repository",
        default="https://pypi.org/simple",
        help="PyPI repository URL (default: PyPI)",
    )

    args = parser.parse_args()

    if check_pypi(args.package_name, args.version, args.repository):
        sys.exit(0)
    else:
        print(
            f"Timeout: Version {args.version} did not appear on {args.repository} within 5 minutes."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
