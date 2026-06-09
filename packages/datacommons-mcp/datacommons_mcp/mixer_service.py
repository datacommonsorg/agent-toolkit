# Copyright 2026 Google LLC.
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
Service layer for calling Mixer-side agent APIs.
"""

from typing import Any

from datacommons_mcp.app import app


async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    child_place_type: str | None = None,
    source_override: str | None = None,
    date: str | None = None,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> dict[str, Any]:
    """Fetches observations via the Mixer-side agent/get_observations endpoint."""
    payload = {
        "variable_dcid": variable_dcid,
        "place_dcid": place_dcid,
        "child_place_type": child_place_type,
        "source_override": source_override,
        "date": date,
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
    }
    return await app.mixer_client.post("agent/get_observations", payload)


async def search_indicators(
    query: str,
    places: list[str] | None = None,
    parent_place: str | None = None,
    per_search_limit: int = 10,
    include_topics: bool = True,
) -> dict[str, Any]:
    """Searches for indicators via the Mixer-side agent/search_indicators endpoint."""
    payload = {
        "query": query,
        "places": places or [],
        "parent_place": parent_place,
        "per_search_limit": per_search_limit,
        "include_topics": include_topics,
    }
    return await app.mixer_client.post("agent/search_indicators", payload)
