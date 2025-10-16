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

import httpx
import logging
from datacommons_client.models.observation import Observation

from datacommons_mcp.data_models.observations import DateRange, ObservationDate
from datacommons_mcp.exceptions import APIKeyValidationError, InvalidAPIKeyError


async def validate_api_key(api_key: str) -> bool:
    """
    Validates the Data Commons API key by making a simple API call.

    Args:
        api_key: The Data Commons API key to validate.

    Returns:
        True if the API key is valid.

    Raises:
        InvalidAPIKeyError: If the API key is invalid (4xx error).
        APIKeyValidationError: For other network-related validation errors.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.datacommons.org/v2/node?nodes=geoId/06",
                headers={"X-API-Key": api_key},
            )
            if 400 <= response.status_code < 500:
                raise InvalidAPIKeyError(
                    f"API key is invalid or has expired. Status: {response.status_code}"
                )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise APIKeyValidationError(
                f"Failed to validate API key due to a server error: {e}"
            )
        except httpx.RequestError as e:
            raise APIKeyValidationError(
                f"Failed to validate API key due to a network error: {e}"
            )
    logging.info("Data Commons API key validation successful.")
    return True


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
