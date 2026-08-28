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

from unittest.mock import MagicMock, patch

import pytest
import requests
from datacommons_mcp.exceptions import APIKeyValidationError, InvalidAPIKeyError
from datacommons_mcp.utils import (
    VALIDATION_API_PATH,
    _get_gcs_client,
    read_external_content,
    read_package_content,
    validate_api_key,
)

TEST_ROOT = "https://test.api.datacommons.org"


class TestValidateAPIKey:
    def test_validate_api_key_success(self, requests_mock):
        url = f"{TEST_ROOT}{VALIDATION_API_PATH}"
        requests_mock.get(url, status_code=200)
        api_key_to_test = "my-test-api-key"
        validate_api_key(api_key_to_test, TEST_ROOT)
        assert requests_mock.last_request.headers["X-API-Key"] == api_key_to_test

    def test_validate_api_key_invalid(self, requests_mock):
        url = f"{TEST_ROOT}{VALIDATION_API_PATH}"
        requests_mock.get(url, status_code=403)
        with pytest.raises(InvalidAPIKeyError):
            validate_api_key("invalid_key", TEST_ROOT)

    def test_validate_api_key_network_error(self, requests_mock):
        url = f"{TEST_ROOT}{VALIDATION_API_PATH}"
        requests_mock.get(
            url,
            exc=requests.exceptions.RequestException("Network error"),
        )
        with pytest.raises(APIKeyValidationError):
            validate_api_key("any_key", TEST_ROOT)


class TestReadContent:
    @pytest.fixture
    def mock_gcs(self):
        with (
            patch("google.cloud.storage.Client") as mock_client_class,
            patch("google.cloud.storage.Blob.from_string") as mock_from_string,
        ):
            _get_gcs_client.cache_clear()
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            mock_blob = MagicMock()
            mock_from_string.return_value = mock_blob
            mock_blob.download_as_text.return_value = "gcs content"

            yield mock_client, mock_from_string, mock_blob

    def test_read_external_content_success(self, tmp_path, create_test_file):
        create_test_file("test.md", "content")
        assert read_external_content(str(tmp_path), "test.md") == "content"

    def test_read_external_content_subdir(self, tmp_path, create_test_file):
        create_test_file("subdir/test.md", "content")
        assert read_external_content(str(tmp_path), "subdir/test.md") == "content"

    def test_read_external_content_missing(self, tmp_path):
        assert read_external_content(str(tmp_path), "missing.md") is None

    def test_read_external_content_gcs_success(self, mock_gcs):
        mock_client, mock_from_string, mock_blob = mock_gcs
        mock_blob.download_as_text.return_value = "custom content 1"

        content = read_external_content("gs://my-bucket/path", "test.md")

        assert content == "custom content 1"
        mock_from_string.assert_called_once_with(
            "gs://my-bucket/path/test.md", client=mock_client
        )

    def test_read_external_content_gcs_success_no_prefix(self, mock_gcs):
        mock_client, mock_from_string, mock_blob = mock_gcs
        mock_blob.download_as_text.return_value = "custom content 2"

        content = read_external_content("gs://my-bucket", "test.md")

        assert content == "custom content 2"
        mock_from_string.assert_called_once_with(
            "gs://my-bucket/test.md", client=mock_client
        )

    def test_read_external_content_gcs_not_found(self, mock_gcs):
        from google.cloud.exceptions import NotFound

        mock_client, mock_from_string, mock_blob = mock_gcs
        mock_blob.download_as_text.side_effect = NotFound("Blob not found")

        content = read_external_content("gs://my-bucket", "test.md")

        assert content is None
        mock_from_string.assert_called_once_with(
            "gs://my-bucket/test.md", client=mock_client
        )

    def test_read_external_content_gcs_failure(self, mock_gcs):
        mock_client, mock_from_string, mock_blob = mock_gcs
        mock_blob.download_as_text.side_effect = Exception("GCS error")

        content = read_external_content("gs://my-bucket", "test.md")

        assert content is None
        mock_from_string.assert_called_once_with(
            "gs://my-bucket/test.md", client=mock_client
        )

    def test_read_package_content_success(self):
        content = read_package_content("datacommons_mcp.instructions", "server.md")
        assert "Data Commons" in content

    def test_read_package_content_missing(self):
        content = read_package_content(
            "datacommons_mcp.instructions", "non_existent_file.md"
        )
        assert content == ""
