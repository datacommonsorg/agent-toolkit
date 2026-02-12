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
from pathlib import Path

import requests
from datacommons_client.models.observation import Observation

from datacommons_mcp.data_models.observations import DateRange, ObservationDate
from datacommons_mcp.exceptions import APIKeyValidationError, InvalidAPIKeyError

logger = logging.getLogger(__name__)

VALIDATION_API_PATH = "/v2/node?nodes=geoId/06"


def validate_api_key(api_key: str, validation_api_root: str) -> None:
    """
    Validates the Data Commons API key by making a simple API call.

    Args:
        api_key: The Data Commons API key to validate.

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


def filter_by_date(
    observations: list[Observation], date_filter: DateRange | None
) -> list[Observation]:
    """
    Filters a list of observations to include only those fully contained
    within the specified date range.
    """
    if not date_filter:
        return observations.copy()

    # The dates in date_filter are already normalized by its validator.
    range_start = date_filter.start_date
    range_end = date_filter.end_date

    filtered_list = []
    for obs in observations:
        # Parse the observation's date interval. The result will be cached.
        obs_date = ObservationDate.parse_date(obs.date)

        # Lexicographical comparison is correct for YYYY-MM-DD format.
        if range_start and obs_date < range_start:
            continue
        if range_end and obs_date > range_end:
            continue
        filtered_list.append(obs)

    return filtered_list


def read_external_content(base_path: str, filename: str) -> str | None:
    """Reads content from an external location (currently only local paths).

    Args:
        base_path: The base directory to look in.
        filename: The name of the file to read (relative to base_path). Can include
            subdirectories (e.g. "tools/search_indicators.md").

    Returns:
        The content of the file as a string, or None if the file does not exist
        or cannot be read.

    Example:
        >>> content = read_external_content("/path/to/instructions", "server.md")
    """
    # TODO: Add support for GCS if needed. This is useful for Custom DCs deployed in the cloud.
    try:
        path = Path(base_path) / filename
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(
            "Failed to read external instruction %s from %s: %s", filename, base_path, e
        )
    return None


def read_package_content(package: str, filename: str) -> str:
    """Reads content from the package resources.

    Args:
        package: The python package to read from (e.g. "datacommons_mcp.instructions").
        filename: The name of the resource to read. Can include subdirectories
            (e.g. "tools/search_indicators.md").

    Returns:
        The content of the resource as a string, or an empty string if not found.

    Example:
        >>> content = read_package_content("datacommons_mcp.instructions", "server.md")
    """
    try:
        # Handle potential subdirectories in filename (e.g. tools/foo.md)
        parts = filename.split("/")
        # Start at instructions package
        resource = importlib.resources.files(package)

        # Traverse down the path
        for part in parts:
            resource = resource.joinpath(part)

        if resource.is_file():
            return resource.read_text(encoding="utf-8")
        else:
            logger.warning("Instruction resource %s not found in package", filename)
            return ""

    except Exception as e:
        logger.warning("Failed to load instruction %s: %s", filename, e)
        return ""
