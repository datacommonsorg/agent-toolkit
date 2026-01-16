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

import logging

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
