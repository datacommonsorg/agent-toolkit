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
def clean_env():
    """
    Automatically clear environment variables for all tests to ensure
    tests are hermetic and don't depend on the host environment.
    """
    with patch.dict(os.environ, {}, clear=True):
        yield


@pytest.fixture(autouse=True)
def mock_load_dotenv():
    """
    Automatically mock load_dotenv for all tests to prevent
    loading environment variables from local .env files.
    """
    with patch("datacommons_mcp.cli.load_dotenv"):
        yield


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """A fixture to isolate tests from .env files and existing env vars."""
    monkeypatch.chdir(tmp_path)

    # This inner function will be the fixture's return value
    def _patch_env(env_vars):
        return patch.dict(os.environ, env_vars, clear=True)

    return _patch_env
