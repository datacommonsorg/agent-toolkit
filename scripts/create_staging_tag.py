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

import os
import subprocess
import sys

"""
Helper script to automate the creation of staging tags (Release Candidates).
It calculates the next sequential RC version (e.g., v1.1.3rc2) using get_next_version.py,
prompts for confirmation, and pushes the tag to origin to trigger the Staging pipeline.

Usage: python3 scripts/create_staging_tag.py
"""


def run_command(cmd: str, *, capture: bool = True) -> str | int:
    try:
        if capture:
            return subprocess.check_output(cmd, shell=True).decode().strip()  # noqa: S602
        return subprocess.check_call(cmd, shell=True)  # noqa: S602
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        sys.exit(e.returncode)


def main() -> None:
    print("Finding next Staging (RC) tag...")

    # Use the existing helper script to get the tag
    script_path = os.path.join(os.path.dirname(__file__), "get_next_version.py")
    try:
        cmd = f"python3 {script_path} --type rc"
        raw_tag = run_command(cmd)

        # Ensure it starts with v
        tag = f"v{raw_tag}" if not raw_tag.startswith("v") else raw_tag

    except Exception as e:
        print(f"Failed to calculate next version: {e}")
        sys.exit(1)

    print(f"\nProposing new tag: \033[1;32m{tag}\033[0m")

    confirm = input("Do you want to create and push this tag? (y/n): ")
    if confirm.lower() != "y":
        print("Aborted.")
        sys.exit(0)

    print(f"Creating tag {tag}...")
    run_command(f"git tag {tag}", capture=False)

    print(f"Pushing tag {tag} to origin...")
    run_command(f"git push origin {tag}", capture=False)

    print(f"\n\033[1;32mSuccess! Staging build triggered for {tag}.\033[0m")
    print(
        "View build status at: https://console.cloud.google.com/cloud-build/builds?project=datcom-ci"
    )


if __name__ == "__main__":
    main()
