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

import asyncio

from datacommons_mcp.clients import MultiDCClient
from datacommons_mcp.data_models.observations import (
    DateRange,
    ObservationPeriod,
    ObservationToolRequest,
    ObservationToolResponse,
)
from datacommons_mcp.exceptions import NoDataFoundError


async def _build_observation_request(
    client: MultiDCClient,
    variable_dcid: str | None = None,
    variable_desc: str | None = None,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    facet_id_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ObservationToolRequest:
    """
    Creates an ObservationRequest from the raw inputs provided by a tool call.
    This method contains the logic to resolve names to DCIDs and structure the data.
    """
    # 0. Perform inital validations
    if not (variable_desc or variable_dcid):
        raise ValueError("Specify either 'variable_desc' or 'variable_dcid'.")

    if not (place_name or place_dcid):
        raise ValueError("Specify either 'place_name' or 'place_dcid'.")

    if (not period) and (bool(start_date) ^ bool(end_date)):
        raise ValueError(
            "Both 'start_date' and 'end_date' are required to specify a custom date range."
        )

    # 2. Get observation period and date filters
    date_filter = None
    if not (period or (start_date and end_date)):
        observation_period = ObservationPeriod.LATEST
    elif period:
        observation_period = ObservationPeriod(period)
    else:  # A date range is provided
        observation_period = ObservationPeriod.ALL
        date_filter = DateRange(start_date=start_date, end_date=end_date)

    # 3. Resolve variable and place DCIDs
    resolve_tasks = {}
    if not variable_dcid:
        resolve_tasks["sv_search"] = client.search_svs([variable_desc])
    if not place_dcid:
        resolve_tasks["place_search"] = client.base_dc.search_places([place_name])

    if resolve_tasks:
        # Use asyncio.gather on the values (coroutines) of the tasks dict
        task_coroutines = list(resolve_tasks.values())
        task_results = await asyncio.gather(*task_coroutines)
        # Map results back to their keys
        results = dict(zip(resolve_tasks.keys(), task_results, strict=True))
        # Parse resolved stat vars (if any)
        if "sv_search" in resolve_tasks:
            variable_dcid = (
                results.get("sv_search", {}).get(variable_desc, {}).get("SV")
            )
            if not variable_dcid:
                raise NoDataFoundError(
                    f"No statistical variables found matching '{variable_desc}'."
                )

        # Parse resolved places (if any)
        if "place_search" in resolve_tasks:
            place_dcid = results.get("place_search", {}).get(place_name)
            if not place_dcid:
                raise NoDataFoundError(f"No place found matching '{place_name}'.")

    # 3. Return an instance of the class
    return ObservationToolRequest(
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        child_place_type=child_place_type,
        facet_ids=[facet_id_override] if facet_id_override else None,
        observation_period=observation_period,
        date_filter=date_filter,
    )


async def get_observations(
    client: MultiDCClient,
    variable_dcid: str | None = None,
    variable_desc: str | None = None,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    facet_id_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ObservationToolResponse:
    """
    Builds the request, fetches the data, and returns the final response.
    This is the main entry point for the observation service.
    """
    observation_request = await _build_observation_request(
        client=client,
        variable_dcid=variable_dcid,
        variable_desc=variable_desc,
        place_dcid=place_dcid,
        place_name=place_name,
        child_place_type=child_place_type,
        facet_id_override=facet_id_override,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    return await client.fetch_obs(observation_request)
