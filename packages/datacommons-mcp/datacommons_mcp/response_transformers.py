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
"""
Response transformers module for Data Commons API responses.
Contains functions for converting API responses into human-readable text format.
"""

import calendar


def _is_within_range(observation_date: str, date_range: tuple[str, str] | None) -> bool:
    """
    Checks if an observation date is within a given date range, inclusive.

    This function correctly handles partial dates in 'YYYY', 'YYYY-MM', or
    'YYYY-MM-DD' format by interpreting them as date intervals.

    Args:
        observation_date: The date to check.
        date_range: A tuple containing the start and end date of the range.

    Returns:
        True if the observation date is within the range, False otherwise.
    """

    def _get_earliest_date(date_str: str) -> str:
        """Converts a partial date string to its earliest possible full date."""
        parts = date_str.split("-")
        year = int(parts[0])
        if len(parts) == 1:  # 'YYYY'
            return f"{year:04d}-01-01"
        month = int(parts[1])
        if len(parts) == 2:  # 'YYYY-MM'
            return f"{year:04d}-{month:02d}-01"
        day = int(parts[2])  # 'YYYY-MM-DD'
        return f"{year:04d}-{month:02d}-{day:02d}"

    def _get_latest_date(date_str: str) -> str:
        """Converts a partial date string to its latest possible full date."""
        parts = date_str.split("-")
        year = int(parts[0])
        if len(parts) == 1:  # 'YYYY'
            return f"{year:04d}-12-31"
        month = int(parts[1])
        if len(parts) == 2:  # 'YYYY-MM'
            _, last_day = calendar.monthrange(year, month)
            return f"{year:04d}-{month:02d}-{last_day:02d}"
        day = int(parts[2])  # 'YYYY-MM-DD'
        return f"{year:04d}-{month:02d}-{day:02d}"

    if not date_range:
        return True

    range_start_str, range_end_str = date_range

    # The effective range is from the earliest possible start date to the latest possible end date.
    effective_range_start = _get_earliest_date(range_start_str)
    effective_range_end = _get_latest_date(range_end_str)

    # The observation's own interval must be fully contained within the effective range.
    observation_start = _get_earliest_date(observation_date)
    observation_end = _get_latest_date(observation_date)

    # Lexicographical comparison works perfectly for 'YYYY-MM-DD' formatted strings.
    return (
        effective_range_start <= observation_start
        and observation_end <= effective_range_end
    )


def transform_obs_response(
    api_response: dict,
    get_dcid_names_func: callable,
    other_dcids_to_lookup: list[str] = None,
    facet_id_override: str = None,
    date_filter: tuple[str, str] = None,
) -> dict:
    """
    Transforms a Data Commons API v2 observation response into an LLM-friendly format.
    The response is bucketed by variable. For each variable, it returns data
    from a single source. If a facet_id_override is provided, that source is used.
    Otherwise, the source with the highest overall observation count is chosen.
    All source metadata is denormalized and embedded directly in the response.

    Args:
        api_response: The raw JSON dictionary response from the Data Commons
                      v2/observation API.
        get_dcid_names_func: A function that accepts a list of DCID strings and
                             returns a dictionary mapping those DCIDs to their
                             human-readable names.
        other_dcids_to_lookup: A list of DCIDs to lookup names for.
        facet_id_override: An optional facet ID to force the selection of a
                           specific data source.
        date_filter: The start and end of date range to filter the observations down to.

    Returns:
        A dictionary in the new, LLM-friendly format, structured as follows:
        {
            "dc_provider": "...",
            "lookups": {
                "id_name_mappings": { ... }
            },
            "data_by_variable": {
                "variable_id_1": {
                    "source": {
                        "facet_id": "best_facet_id",
                        "provenance_url": "...",
                        "import_method": "...",
                        "observation_count": 120
                    },
                    "observations": [
                        ["entity_id_1", "date_1", "value_1"],
                        ["entity_id_2", "date_2", "value_2"]
                    ],
                    "other_available_sources": [
                        {
                            "facet_id": "other_facet_456",
                            "provenance_url": "...",
                            "import_method": "...",
                            "observation_count": 50
                        }
                    ]
                }
            }
        }
    """

    final_transformed_response = {
        "dc_provider": api_response.get("dc_provider", ""),
        "lookups": {
            "id_name_mappings": {},
        },
        "data_by_variable": {},
    }

    all_dcids_to_lookup = set(other_dcids_to_lookup) if other_dcids_to_lookup else set()
    source_metadata_by_facet_id = {}
    if api_response and "facets" in api_response:
        source_metadata_by_facet_id = api_response["facets"]

    if api_response and "byVariable" in api_response:
        for variable_id, var_data in api_response["byVariable"].items():
            all_dcids_to_lookup.add(variable_id)

            # Temp structure to aggregate data per facet across all entities
            temp_data_by_facet = {}

            if var_data and "byEntity" in var_data:
                for entity_id, entity_data in var_data["byEntity"].items():
                    all_dcids_to_lookup.add(entity_id)

                    if entity_data and "orderedFacets" in entity_data:
                        for facet_container in entity_data["orderedFacets"]:
                            facet_id = facet_container.get("facetId")
                            if not facet_id:
                                continue

                            if facet_id not in temp_data_by_facet:
                                temp_data_by_facet[facet_id] = {"observations": []}

                            for obs in facet_container.get("observations", []):
                                if (
                                    obs.get("date") is not None
                                    and obs.get("value") is not None
                                    and _is_within_range(obs["date"], date_filter)
                                ):
                                    temp_data_by_facet[facet_id]["observations"].append(
                                        [entity_id, obs["date"], obs["value"]]
                                    )

            if not temp_data_by_facet:
                continue

            # Add observation counts to each facet's data
            for data in temp_data_by_facet.values():
                data["observation_count"] = len(data["observations"])

            # Determine the best facet
            best_facet_id = None
            if facet_id_override and facet_id_override in temp_data_by_facet:
                best_facet_id = facet_id_override
            else:
                # Find by max observation count if no valid override
                max_obs_count = -1
                for facet_id, data in temp_data_by_facet.items():
                    if data["observation_count"] > max_obs_count:
                        max_obs_count = data["observation_count"]
                        best_facet_id = facet_id

            # Construct the response for the current variable
            variable_data = {}
            other_sources_for_var = []

            for facet_id, data in temp_data_by_facet.items():
                # Get the full, denormalized source info
                source_info = source_metadata_by_facet_id.get(facet_id, {}).copy()
                source_info["facet_id"] = facet_id
                source_info["observation_count"] = data["observation_count"]

                if facet_id == best_facet_id:
                    variable_data["source"] = source_info
                    variable_data["observations"] = data["observations"]
                else:
                    other_sources_for_var.append(source_info)

            if "source" in variable_data:
                variable_data["other_available_sources"] = other_sources_for_var
                final_transformed_response["data_by_variable"][variable_id] = (
                    variable_data
                )

    # Call the provided function to get id_name_mappings for all collected DCIDs
    if all_dcids_to_lookup:
        final_transformed_response["lookups"]["id_name_mappings"] = get_dcid_names_func(
            list(all_dcids_to_lookup)
        )

    return final_transformed_response
