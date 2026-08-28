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

import importlib.resources
import logging
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from google.cloud import storage

from datacommons_mcp.exceptions import APIKeyValidationError, InvalidAPIKeyError

logger = logging.getLogger(__name__)

VALIDATION_API_PATH = "/v2/node?nodes=geoId/06"


def validate_api_key(api_key: str, validation_api_root: str) -> None:
    """
    Validates the Data Commons API key by making a simple API call.

    Args:
        api_key: The Data Commons API key to validate.
        validation_api_root: The root URL for the Data Commons API to validate against.

    Raises:
        InvalidAPIKeyError: If the API key is invalid or has expired.
        APIKeyValidationError: For other network-related validation errors.
    """
    validation_api_url = f"{validation_api_root}{VALIDATION_API_PATH}"
    logger.info("Validating API key with URL: %s", validation_api_url)

    try:
        response = requests.get(
            validation_api_url,
            headers={"X-API-Key": api_key},
            timeout=10,  # 10-second timeout
        )
        if 400 <= response.status_code < 500:
            raise InvalidAPIKeyError(
                f"API key is invalid or has expired. Status: {response.status_code}"
            )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise APIKeyValidationError(
            f"Failed to validate API key due to a server error: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        raise APIKeyValidationError(
            f"Failed to validate API key due to a network error: {e}"
        ) from e

    logger.info("Data Commons API key validation successful.")


@cache
def _get_gcs_client() -> "storage.Client":
    """Returns a cached GCS client instance."""
    # Local import to avoid loading the module unless GCS is required
    from google.cloud import storage

    return storage.Client()


def read_external_content(base_dir: str, filename: str) -> str | None:
    """
    Reads content from an external source, supporting both local filesystem
    paths and Google Cloud Storage (GCS) paths.

    Args:
        base_dir: The base directory path. Can be a local filesystem path
            or a GCS URI (e.g., gs://bucket-name/optional/prefix).
        filename: The relative path to the file from the base directory
            (e.g., server.md or tools/get_observations.md).

    Returns:
        The content of the file as a string if found, None otherwise.
    """
    if base_dir.startswith("gs://"):
        return _read_gcs_content(base_dir, filename)
    return _read_local_content(base_dir, filename)


def _read_local_content(base_dir: str, filename: str) -> str | None:
    """Reads content from a local filesystem path."""
    file_path = Path(base_dir) / filename
    if file_path.is_file():
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("Failed to read external file %s: %s", file_path, e)
            return None
    return None


def _read_gcs_content(gcs_uri: str, filename: str) -> str | None:
    """Reads content from a Google Cloud Storage URI."""
    from google.cloud.exceptions import NotFound
    from google.cloud.storage import Blob

    # Construct the full GCS URI
    # Remove trailing slash from base_uri and leading slash from filename
    clean_base = gcs_uri.rstrip("/")
    clean_filename = filename.lstrip("/")
    full_gcs_path = f"{clean_base}/{clean_filename}"

    logger.debug("Attempting to load custom instructions from GCS: %s", full_gcs_path)

    try:
        client = _get_gcs_client()
        blob = Blob.from_string(full_gcs_path, client=client)
        return blob.download_as_text()
    except NotFound:
        logger.debug("GCS file not found: %s", full_gcs_path)
        return None
    except Exception as e:
        logger.warning("Failed to read GCS file %s: %s", full_gcs_path, e)
        return None


def read_package_content(package: str, filename: str) -> str:
    """
    Reads content from a package resource using importlib.resources.

    Args:
        package: The package name containing the resource (e.g., datacommons_mcp.instructions).
        filename: The relative path to the resource within the package.

    Returns:
        The content of the file as a string, or empty string if not found.
    """
    try:
        # Traverse subdirectories if filename contains path separators
        resource = importlib.resources.files(package)
        for part in Path(filename).parts:
            resource = resource / part

        if resource.is_file():
            return resource.read_text(encoding="utf-8")
        logger.warning(
            "Package resource not found or not a file: %s/%s", package, filename
        )
        return ""
    except Exception as e:
        logger.warning(
            "Failed to read package resource %s/%s: %s", package, filename, e
        )
        return ""
