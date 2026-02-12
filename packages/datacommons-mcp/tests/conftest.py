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
Global pytest configuration and fixtures.

Pytest automatically discovers and loads this file. Fixtures defined here are
available to all tests in this directory and its subdirectories without
needing to import them explicitly.
"""

import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    """
    Automatically clear environment variables and change to a temporary directory
    for all tests. This ensures tests are hermetic and don't depend on the
    host environment or local .env files.
    """
    # Change to a temporary directory to hide local .env files
    monkeypatch.chdir(tmp_path)

    # Clear environment variables
    with patch.dict(os.environ, {}, clear=True):
        yield


@pytest.fixture
def create_test_file(tmp_path):
    """
    Fixture that returns a helper function to create files in tmp_path.
    Usage: create_test_file("path/to/file.txt", "content")
    """

    def _create(filename, content):
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    return _create
