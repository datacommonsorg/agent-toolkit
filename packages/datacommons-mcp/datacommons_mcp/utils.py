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
from collections import defaultdict

from datacommons_client.models.observation import Observation

from datacommons_mcp.data_models.observations import DateRange


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
        obs_start, obs_end = DateRange.parse_interval(obs.date)

        # Lexicographical comparison is correct for YYYY-MM-DD format.
        if range_start <= obs_start and obs_end <= range_end:
            filtered_list.append(obs)

    return filtered_list
