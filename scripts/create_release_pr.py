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
Script to create a version bump PR via Cloud Build.

Usage:
    python scripts/create_release_pr.py --project datcom-ci --type <major|minor|patch>
"""

import argparse
import os
import subprocess
import sys
import tomllib


def get_current_version() -> str:
    pyproject_path = os.path.join(
        os.path.dirname(__file__), "../packages/datacommons-mcp/pyproject.toml"
    )
    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return data["project"]["version"]
    except Exception as e:
        print(f"Error reading version: {e}")
        sys.exit(1)


def bump_version(current_version: str, bump_type: str) -> str:
    major, minor, patch = map(int, current_version.split("."))
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    if bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return current_version


def run_command(cmd: str, *, capture: bool = True, exit_on_error: bool = True) -> str | int:
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
    check_preconditions()
    parser = argparse.ArgumentParser(
        description="Create a version bump PR via Cloud Build"
    )
    parser.add_argument("--project", default="datcom-ci", help="GCP Project ID")
    parser.add_argument("--type", choices=["major", "minor", "patch"], help="Bump type")

    args = parser.parse_args()

    current_version = get_current_version()
    print(f"Current version: {current_version}")

    if not args.type:
        print("Select bump type:")
        print("1. Patch (x.y.z -> x.y.z+1)")
        print("2. Minor (x.y.z -> x.y+1.0)")
        print("3. Major (x.y.z -> x+1.0.0)")
        choice = input("Enter choice [1-3]: ").strip()
        if choice == "1":
            args.type = "patch"
        elif choice == "2":
            args.type = "minor"
        elif choice == "3":
            args.type = "major"
        else:
            print("Invalid choice")
            sys.exit(1)

    new_version = bump_version(current_version, args.type)
    print(f"New Version: {new_version}")

    if input(f"Create PR to bump version to {new_version}? (y/n) ").lower() != "y":
        print("Aborted.")
        sys.exit(0)

    cmd = [
        "gcloud",
        "builds",
        "submit",
        ".",
        "--config",
        "deploy/bump_version.yaml",
        "--project",
        args.project,
        f"--substitutions=_NEW_VERSION={new_version}",
    ]

    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)  # noqa: S603


if __name__ == "__main__":
    main()
