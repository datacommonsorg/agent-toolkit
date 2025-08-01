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

import calendar
from functools import lru_cache

from datacommons_client.models.observation import Observation

from datacommons_mcp.data_models.observations import DateRange
from datacommons_mcp.exceptions import InvalidDateFormatError


@lru_cache(maxsize=128)
def parse_date_interval(date_str: str) -> tuple[str, str]:
    """
    Converts a partial date string into a full (start, end) date tuple.
    Caches results to avoid re-calculating for the same input string.

    Raises:
        InvalidDateFormatError: If the date string format is invalid.
    """
    try:
        parts = date_str.split("-")
        year = int(parts[0])

        if len(parts) == 1:  # 'YYYY'
            return f"{year:04d}-01-01", f"{year:04d}-12-31"

        month = int(parts[1])
        if len(parts) == 2:  # 'YYYY-MM'
            _, last_day = calendar.monthrange(year, month)
            return (
                f"{year:04d}-{month:02d}-01",
                f"{year:04d}-{month:02d}-{last_day:02d}",
            )

        day = int(parts[2])  # 'YYYY-MM-DD'
        full_date = f"{year:04d}-{month:02d}-{day:02d}"
        return full_date, full_date

    except (ValueError, IndexError, calendar.IllegalMonthError) as e:
        # Catch multiple potential errors and raise a single, clear custom exception.
        raise InvalidDateFormatError(f"Invalid date format: '{date_str}'") from e


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
        obs_start, obs_end = parse_date_interval(obs.date)

        # Lexicographical comparison is correct for YYYY-MM-DD format.
        if range_start <= obs_start and obs_end <= range_end:
            filtered_list.append(obs)

    return filtered_list
