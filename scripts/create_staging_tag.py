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

from get_next_version import prompt_for_bump_type

"""
Helper script to automate the creation of staging tags (Release Candidates).
It calculates the next sequential RC version (e.g., v1.1.3rc2) using get_next_version.py,
prompts for confirmation, and pushes the tag to origin to trigger the Staging pipeline.

Usage: python3 scripts/create_staging_tag.py --bump-type <major|minor|patch|none>
"""


def run_command(
    cmd: str, *, capture: bool = True, exit_on_error: bool = True
) -> str | int:
    try:
        if capture:
            return subprocess.check_output(cmd, shell=True).decode().strip()  # noqa: S602
        return subprocess.check_call(cmd, shell=True)  # noqa: S602
    except subprocess.CalledProcessError as e:
        if not exit_on_error:
            raise e
        print(f"Error running command: {cmd}")
        sys.exit(e.returncode)


def check_preconditions() -> None:
    print("Checking preconditions...")

    # 1. Check branch is main
    current_branch = str(run_command("git branch --show-current", capture=True))
    if current_branch != "main":
        print(
            f"\033[1;31mError: Script must be run from 'main' branch. Current branch: {current_branch}\033[0m"
        )
        sys.exit(1)

    # 2. Check for uncommitted changes
    status = str(run_command("git status --porcelain", capture=True))
    if status:
        print(
            "\033[1;31mError: Working directory is not clean. Please commit or stash changes.\033[0m"
        )
        print(status)
        sys.exit(1)


def main() -> None:
    import argparse
    import tomllib

    parser = argparse.ArgumentParser(description="Create a staging tag (RC)")
    parser.add_argument(
        "--commit",
        help="Specific commit hash to tag (defaults to HEAD). If provided, version is read from this commit.",
    )
    parser.add_argument(
        "--bump-type",
        choices=["none", "major", "minor", "patch"],
        help="Bump type",
        default="none",
    )
    args = parser.parse_args()

    commit_hash = args.commit
    if commit_hash:
        try:
            run_command(f"git cat-file -t {commit_hash}", capture=True)
            print(f"Using specified commit: {commit_hash}")
        except subprocess.CalledProcessError:
            print(f"\033[1;31mError: Commit {commit_hash} not found.\033[0m")
            sys.exit(1)
    else:
        check_preconditions()
        print("Using current HEAD.")

    if args.bump_type == "none":
        print(
            "\nDo you want to bump the base version before creating the RC? (y/N) [n]: ",
            end="",
        )
        bump_choice = input().strip().lower()
        if bump_choice == "y":
            args.bump_type = prompt_for_bump_type()

    print("Finding next Staging (RC) tag...")

    base_version_arg = ""
    if commit_hash:
        # Read pyproject.toml from that commit
        try:
            pyproject_content = run_command(
                f"git show {commit_hash}:packages/datacommons-mcp/pyproject.toml",
                capture=True,
            )
            if isinstance(pyproject_content, bytes):
                pyproject_content = pyproject_content.decode()
            elif isinstance(pyproject_content, int):
                print("Error reading file content.")
                sys.exit(1)

            project_data = tomllib.loads(pyproject_content)
            base_version = project_data["project"]["version"]
            base_version_arg = f"--base-version {base_version}"
            print(f"Read version {base_version} from commit {commit_hash}")
        except Exception as e:
            print(f"Failed to read version from commit {commit_hash}: {e}")
            sys.exit(1)

    # Use the existing helper script to get the tag
    script_path = os.path.join(os.path.dirname(__file__), "get_next_version.py")
    try:
        cmd = f"python3 {script_path} --type rc {base_version_arg} --bump-type {args.bump_type}"
        raw_tag = run_command(cmd)

        # Ensure it starts with v
        tag = f"v{raw_tag}" if not raw_tag.startswith("v") else raw_tag

    except Exception as e:
        print(f"Failed to calculate next version: {e}")
        sys.exit(1)

    print(f"\nProposing new tag: \033[1;32m{tag}\033[0m")
    if commit_hash:
        print(f"Target Commit: \033[1;33m{commit_hash}\033[0m")

    confirm = input("Do you want to create and push this tag? (y/n): ")
    if confirm.lower() != "y":
        print("Aborted.")
        sys.exit(0)

    print(f"Creating tag {tag}...")
    if commit_hash:
        run_command(f"git tag {tag} {commit_hash}", capture=False)
    else:
        run_command(f"git tag {tag}", capture=False)

    print(f"Pushing tag {tag} to upstream...")
    try:
        run_command(f"git push upstream {tag}", capture=False, exit_on_error=False)
    except subprocess.CalledProcessError:
        print("\n\033[1;31mError: Failed to push to upstream remote.\033[0m")
        print("Please ensure you have the 'upstream' remote configured:")
        print(
            "  git remote add upstream https://github.com/datacommonsorg/agent-toolkit.git"
        )
        print("  git remote -v")
        sys.exit(1)

    print(f"\n\033[1;32mSuccess! Staging build triggered for {tag}.\033[0m")
    print(
        'View build status at: https://pantheon.corp.google.com/cloud-build/builds;region=global?query=trigger_id="82c43c13-4c16-4527-8110-f4abf72cd9d5"&project=datcom-ci'
    )


if __name__ == "__main__":
    main()
