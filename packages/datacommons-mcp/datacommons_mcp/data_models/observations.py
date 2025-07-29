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
from enum import Enum

from datacommons_client.models.observation import Facet, Observation, ObservationDate
from datacommons_mcp.clients import MultiDCClient
from datacommons_mcp.constants import BASE_DC_ID
from datacommons_mcp.exceptions import NoDataFoundError
from pydantic import BaseModel, Field, model_validator


class ObservationPeriod(ObservationDate):
    """Wrapper to rename datacommons_client object to avoid confusion."""


class DateRange(BaseModel):
    "Accepted formats: YYYY or YYYY-MM or YYYY-MM-DD"

    start_date: str
    end_date: str


class ObservationRequest(BaseModel):
    variable_dcid: str
    place_dcid: str
    child_place_type_dcid: str | None = None
    facet_ids: list[str] | None = None
    date: ObservationPeriod | str = None
    date_filter: DateRange | None = None

    @classmethod
    async def from_tool_inputs(
        cls,
        client: MultiDCClient,
        variable_desc: str | None = None,
        variable_dcid: str | None = None,
        place_name: str | None = None,
        place_dcid: str | None = None,
        child_place_type: str | None = None,
        facet_id_override: str | None = None,
        period: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> "ObservationRequest":
        """
        Creates an ObservationRequest from the raw inputs provided by a tool call.
        This method contains the logic to resolve names to DCIDs and structure the data.
        """
        # 0. Perform inital validations
        if not (variable_desc or variable_dcid):
            raise ValueError("Specify either 'variable_desc' or 'variable_dcid'.")

        if not (place_name or place_dcid):
            raise ValueError("Specify either 'place_name' or 'place_dcid'.")

        # NEXT: check for period / date range validity and fill in

        # 1. Resolve variable and place DCIDs (this logic might involve API calls)

        # TODO(clincoln8): Defaulting to base dc id when a variable_dcid seems incorrect.
        resolved_client_id = BASE_DC_ID
        resolve_tasks = {}
        # Start tasks
        if not variable_dcid:
            resolve_tasks["sv_search"] = client.search_svs([variable_desc])
        if not place_dcid:
            resolve_tasks["place_search"] = client.base_dc.search_places([place_name])

        # Wait for tasks to finish
        if resolve_tasks:
            # Use asyncio.gather on the values (coroutines) of the tasks dict
            task_coroutines = list(resolve_tasks.values())
            task_results = await asyncio.gather(*task_coroutines)
            # Map results back to their keys
            results = dict(zip(resolve_tasks.keys(), task_results, strict=False))

            if resolve_variable_result := results.get("sv_search", {}):
                variable_dcid = resolve_variable_result.get(variable_desc, {}).get(
                    "SV", ""
                )

                if not variable_dcid:
                    # TODO(clincoln8): Add instruction for potenital actions following this response.
                    raise NoDataFoundError(
                        f"No statistical variables found matching '{variable_desc}'."
                    )

                resolved_client_id = resolve_variable_result.get(variable_desc, {}).get(
                    "dc_id"
                )
            if resolve_places_result := results.get("place_search", {}):
                place_dcid = resolve_places_result.get(place_name)
                if not place_dcid:
                    # TODO(clincoln8): Add instruction for potenital actions following this response.
                    raise NoDataFoundError(f"No place found matching '{place_name}'.")

        # 2. Structure the date information
        final_date = create_observation_period(
            period=period, start=start_date, end=end_date
        )

        # 3. Handle optional fields
        facets = [facet_id_override] if facet_id_override else None

        # 4. Return an instance of the class
        return cls(
            variable_dcid=final_variable_dcid,
            place_dcid=final_place_dcid,
            child_place_type_dcid=child_place_type,  # Assuming this needs resolving too
            facet_ids=facets,
            date=final_date,
        )
