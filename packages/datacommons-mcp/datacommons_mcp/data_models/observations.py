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
import calendar
from functools import lru_cache
from typing import TypeAlias

from datacommons_client.endpoints.response import ObservationResponse
from datacommons_client.models.observation import Facet, Observation, ObservationDate
from datacommons_mcp.clients import MultiDCClient
from datacommons_mcp.exceptions import InvalidDateFormatError, NoDataFoundError
from pydantic import BaseModel, Field

DateFilter: TypeAlias = tuple[str, str]


class ObservationPeriod(ObservationDate):
    """Wrapper to rename datacommons_client object to avoid confusion."""


class DateRange(BaseModel):
    "Accepted formats: YYYY or YYYY-MM or YYYY-MM-DD"

    start_date: str
    end_date: str


class ObservationToolRequest(BaseModel):
    variable_dcid: str
    place_dcid: str
    child_place_type_dcid: str | None = None
    facet_ids: list[str] | None = None
    observation_period: ObservationPeriod | str = None
    date_filter: DateRange | None = None
    dc_client_id: str | None = None

    @classmethod
    async def from_tool_inputs(
        cls,
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
    ) -> "ObservationToolRequest":
        """
        Creates an ObservationRequest from the raw inputs provided by a tool call.
        This method contains the logic to resolve names to DCIDs and structure the data.
        """
        # 0. Perform inital validations
        if not (variable_desc or variable_dcid):
            raise ValueError("Specify either 'variable_desc' or 'variable_dcid'.")

        if not (place_name or place_dcid):
            raise ValueError("Specify either 'place_name' or 'place_dcid'.")

        if not period and (bool(start_date) ^ bool(end_date)):
            raise ValueError(
                "Both 'start_date' and 'end_date' are required to specify a custom date range."
            )

        # 1. Resolve variable and place DCIDs
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

            if resolve_places_result := results.get("place_search", {}):
                place_dcid = resolve_places_result.get(place_name)
                if not place_dcid:
                    # TODO(clincoln8): Add instruction for potenital actions following this response.
                    raise NoDataFoundError(f"No place found matching '{place_name}'.")

        # 2. Get observation period and date filters
        date_filter = None
        if not (period or (start_date and end_date)):
            observation_period = ObservationPeriod.LATEST
        elif period:
            observation_period = ObservationPeriod(period)
        elif start_date == end_date:
            observation_period = start_date
        else:
            observation_period = ObservationPeriod.ALL
            date_filter = DateRange(start_date=start_date, end_date=end_date)

        # 4. Return an instance of the class
        return cls(
            variable_dcid=variable_dcid,
            place_dcid=place_dcid,
            child_place_type=child_place_type,
            facet_ids=[facet_id_override],
            observation_period=observation_period,
            date_filter=date_filter,
        )


class SourceMetadata(Facet):
    dc_client_id: str
    earliest_date: str
    latest_date: str
    total_observations: int


class VariableSeries(BaseModel):
    variable_dcid: str
    source_metadata: SourceMetadata
    observations: list[Observation]
    alternative_sources: list[SourceMetadata] = Field(default_factory=list)


class PlaceData(BaseModel):
    place_dcid: str = Field(default_factory=str)
    place_name: str = Field(default_factory=str)
    variable_series: dict[str, VariableSeries] = Field(default_factory=dict)


class ObservationApiResponse(ObservationResponse):
    """Wrapper to rename DC Client ObservationResponse to avoid confusion."""


class ObservationToolResponse(BaseModel):
    place_data: dict[str, PlaceData] = Field(default_factory=dict)

    def merge_fetch_observation_response(
        self,
        api_response: ObservationApiResponse,
        api_client_id: str,
        selected_facet_ids: list[str] | None = None,
        date_filter: DateRange | None = None,
    ) -> None:
        flattened_api_response = api_response.get_data_by_entity()
        for variable_dcid, api_variable_data in flattened_api_response.items():
            for place_dcid, api_place_data in api_variable_data.items():
                # Get or initialize the place_data entry in final response
                if place_dcid not in self.place_data:
                    self.place_data[place_dcid] = PlaceData(place_dcid=place_dcid)
                place_data = self.place_data[place_dcid]

                first_obs = None
                sources = []

                for facet in api_place_data.orderedFacets:
                    if selected_facet_ids and facet not in selected_facet_ids:
                        continue

                    facet_metadata = api_response.facets.get(facet.facetId)
                    metadata = SourceMetadata(
                        **facet_metadata.to_dict(),
                        dc_client_id=api_client_id,
                        earliest_date=facet.earliestDate,
                        latest_date=facet.latestDate,
                        total_observations=facet.obsCount,
                    )
                    sources.append(metadata)
                    if not first_obs and (
                        filtered_obs := filter_by_date(facet.observations, date_filter)
                    ):
                        first_obs = filtered_obs

                # Append alternative sources to an existing variable series
                if variable_dcid in place_data.variable_series:
                    place_data.variable_series[
                        variable_dcid
                    ].alternative_sources.extend(sources)
                # Otherwise create a new variable series with the first facet as the
                # primary one.
                else:
                    if first_obs and sources:
                        place_data.variable_series[variable_dcid] = VariableSeries(
                            variable_dcid=variable_dcid,
                            source_metadata=sources[0],
                            observations=first_obs,
                            alternative_sources=sources[1:],
                        )


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

    range_start, _ = parse_date_interval(date_filter.start_date)
    _, range_end = parse_date_interval(date_filter.end_date)

    filtered_list = []
    for obs in observations:
        # Parse the observation's date interval. The result will be cached.
        obs_start, obs_end = parse_date_interval(obs.date)

        # Lexicographical comparison is correct for YYYY-MM-DD format.
        if range_start <= obs_start and obs_end <= range_end:
            filtered_list.append(obs)

    return filtered_list
