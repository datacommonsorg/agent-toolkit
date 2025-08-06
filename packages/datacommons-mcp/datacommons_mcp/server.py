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
Server module for the DC MCP server.
"""

import asyncio
from asyncore import loop
import types
from typing import Union, get_args, get_origin

from fastmcp import FastMCP
from pydantic import ValidationError

import datacommons_mcp.config as config
from datacommons_mcp.clients import create_clients
from datacommons_mcp.constants import BASE_DC_ID, CUSTOM_DC_ID
from datacommons_mcp.datacommons_chart_types import (
    CHART_CONFIG_MAP,
    DataCommonsChartConfig,
    HierarchyLocation,
    MultiPlaceLocation,
    SinglePlaceLocation,
    SingleVariableChart,
)
from datacommons_mcp.response_transformers import transform_obs_response

# Create clients based on config
multi_dc_client = create_clients(config.CUSTOM_DC_CONFIG)

mcp = FastMCP("DC MCP Server")


@mcp.tool()
async def get_observations(
    variable_desc: str | None = None,
    variable_dcid: str | None = None,
    place_name: str | None = None,
    place_dcid: str | None = None,
    child_place_type: str | None = None,
    facet_id_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Fetches observations for a statistical variable from Data Commons.

    This tool can operate in two primary modes:
    1.  **Single Place Mode**: Get data for one specific place (e.g., "Population of California").
    2.  **Child Places Mode**: Get data for all child places of a certain type within a parent place (e.g., "Population of all counties in California").

    ### Core Logic & Rules

    * **Variable Selection**: You **must** provide either `variable_dcid` or `variable_desc`.
        * **Rule 1 (Preferred)**: If you have a relevant `variable_dcid` from a previous tool call (like `get_available_variables_for_place`), **use it**. This is more precise.
        * **Rule 2 (Fallback)**: If you do not have a known `variable_dcid`, use `variable_desc` with a natural language description (e.g., "median household income").

    * **Place Selection**: You **must** provide either `place_dcid` or `place_name`.
      * **Important Note for Bilateral Data**: When fetching data for bilateral variables (e.g., grants from one country to another), 
      the `variable_dcid` often encodes one of the places (e.g., `CRS_BasicHealth-ODAGrants-BOL` refers to grants *to* Bolivia). 
      In such cases, the `place_dcid` (or `place_name`) parameter in `get_observations` should specify the *other* place involved in the bilateral relationship 
      (e.g., the donor country, such as 'France' for grants *from* France). 
      The `search_topics_and_variables` tool's `places_with_data` field can help identify which place is the appropriate observation source for `place_dcid` (or `place_name`).

    * **Mode Selection**:
        * To get data for the specified place (e.g., California), **do not** provide `child_place_type`.
        * To get data for all its children (e.g., all counties in California), you **must also** provide the `child_place_type` (e.g., "County"). Use the `validate_child_place_types` tool to find valid types.

    * **Data Volume Constraint**: When using **Child Places Mode** (when `child_place_type` is set), you **must** be conservative with your date range to avoid requesting too much data.
        * Avoid requesting `'all'` data via the `period` parameter.
        * **Instead, you must either request the `'latest'` data or provide a specific, bounded date range.**

    * **Date Filtering**: The tool filters observations by date using the following priority:
        1.  **`period`**: If you provide the `period` parameter ('all' or 'latest'), it takes top priority.
        2.  **Date Range**: If `period` is not provided, you must specify a custom range using **both** `start_date` and `end_date`.
            * Dates must be in `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` format.
            * To get data for a single date, set `start_date` and `end_date` to the same value. For example, to get data for 2025, use `start_date="2025"` and `end_date="2025"`.
        3.  **Default Behavior**: If you do not provide **any** date parameters (`period`, `start_date`, or `end_date`), the tool will automatically fetch only the `'latest'` observation.

    Args:
      variable_desc (str, optional): A natural language description of the indicator. Ex: "carbon emissions", "unemployment rate".
      variable_dcid (str, optional): The unique identifier (DCID) of the statistical variable.
      place_name (str, optional): The common name of the place. Ex: "United States", "India", "NYC".
      place_dcid (str, optional): The DCID of the place.
      child_place_type (str, optional): The type of child places to get data for. **Use this to switch to Child Places Mode.**
      facet_id_override (str, optional): An optional facet ID to force the use of a specific data source.
      period (str, optional): A special period filter. Accepts "all" or "latest". Overrides date range.
      start_date (str, optional): The start date for a custom range. **Used only with `end_date` and ignored if `period` is set.**
      end_date (str, optional): The end date for a custom range. **Used only with `start_date` and ignored if `period` is set.**

    Returns:
      dict: A dictionary containing the request status and data.

      **How to Process the Response:**
      1.  **Check Status**: First, check the `status` field. If it's "ERROR" or "NO_DATA_FOUND", inform the user accordingly using the `message`.
      2.  **Extract Data**: The data is inside `data['data_by_variable']`. Each key is a `variable_id`. The `observations` list contains the actual data points: `[entity_id, date, value]`.
      3.  **Make it Readable**: Use the `data['lookups']['id_name_mappings']` dictionary to convert `variable_id` and `entity_id` from cryptic IDs to human-readable names.
    """
    # 1. Input validation
    if not (variable_desc or variable_dcid) or (variable_desc and variable_dcid):
        return {
            "status": "ERROR",
            "message": "Specify either 'variable_desc' or 'variable_dcid', but not both.",
        }

    if not (place_name or place_dcid) or (place_name and place_dcid):
        return {
            "status": "ERROR",
            "message": "Specify either 'place_name' or 'place_dcid', but not both.",
        }

    if not period and (bool(start_date) ^ bool(end_date)):
        return {
            "status": "ERROR",
            "message": "Both 'start_date' and 'end_date' are required to select a date range.",
        }

    filter_dates_post_fetch = False
    if period:
        # If period is provided, use it.
        date = period
    elif start_date != end_date:
        # If date range is provided, fetch all data then filter response
        date = "all"
        filter_dates_post_fetch = True
    elif start_date and end_date:
        # If single date is requested, fetch the specific date
        date = start_date
    else:
        # If neither period nor range are provided, default to latest date
        # TODO(clincoln8): Replace literals with enums in pydantic models.
        date = "latest"

    # 2. Concurrently resolve identifiers if needed
    tasks = {}
    if variable_desc:
        tasks["sv_search"] = multi_dc_client.search_svs([variable_desc])
    if place_name:
        tasks["place_search"] = multi_dc_client.base_dc.search_places([place_name])

    svs = None
    places = None
    if tasks:
        # Use asyncio.gather on the values (coroutines) of the tasks dict
        task_coroutines = list(tasks.values())
        task_results = await asyncio.gather(*task_coroutines)
        # Map results back to their keys
        results = dict(zip(tasks.keys(), task_results, strict=False))
        svs = results.get("sv_search")
        places = results.get("place_search")

    # 3. Process results and set DCIDs
    sv_dcid_to_use = variable_dcid
    place_dcid_to_use = place_dcid

    if svs:
        sv_data = svs.get(variable_desc, {})
        print(f"sv_data: {variable_desc} -> {sv_data}")
        sv_dcid_to_use = sv_data.get("SV", "")

    if places:
        place_dcid_to_use = places.get(place_name, "")
        print(f"place: {place_name} -> {place_dcid_to_use}")

    # 4. Final validation
    if not sv_dcid_to_use or not place_dcid_to_use:
        return {"status": "NO_DATA_FOUND"}

    # 5. Fetch Data
    response = await multi_dc_client.fetch_obs(
        [sv_dcid_to_use], place_dcid_to_use, child_place_type, date
    )

    dc_client = multi_dc_client.custom_dc or multi_dc_client.base_dc
    response["dc_provider"] = dc_client.dc_name

    return {
        "status": "SUCCESS",
        "data": transform_obs_response(
            response,
            dc_client.fetch_entity_names,
            other_dcids_to_lookup=[place_dcid_to_use] if child_place_type else None,
            facet_id_override=facet_id_override,
            date_filter=[start_date, end_date] if filter_dates_post_fetch else None,
        ),
    }


@mcp.tool()
async def validate_child_place_types(
    parent_place_name: str, child_place_types: list[str]
) -> dict[str, bool]:
    """
    Checks which of the child place types are valid for the parent place.

    Use this tool to validate the child place types before calling get_observations_for_child_places.

    Example:
    - For counties in Kenya, you can check for both "County" and "AdministrativeArea1" to determine which is valid.
      i.e. "validate_child_place_types("Kenya", ["County", "AdministrativeArea1"])"

    The full list of valid child place types are the following:
    - AdministrativeArea1
    - AdministrativeArea2
    - AdministrativeArea3
    - AdministrativeArea4
    - AdministrativeArea5
    - Continent
    - Country
    - State
    - County
    - City
    - CensusZipCodeTabulationArea
    - Town
    - Village

    Valid child place types can vary by parent place. Here are hints for valid child place types for some of the places:
    - If parent_place_name is a continent (e.g., "Europe") or the world: "Country"
    - If parent_place_name is the US or a place within it: "State", "County", "City", "CensusZipCodeTabulationArea", "Town", "Village"
    - For all other countries: The tool uses a standardized hierarchy: "AdministrativeArea1" (primary division), "AdministrativeArea2" (secondary division), "AdministrativeArea3", "AdministrativeArea4", "AdministrativeArea5".
      Map commonly used administrative level names to the appropriate administrative area type based on this hierarchy before calling this tool.
      Use these examples as a guide for mapping:
      - For India: States typically map to 'AdministrativeArea1', districts typically map to 'AdministrativeArea2'.
      - For Spain: Autonomous communities typically map to 'AdministrativeArea1', provinces typically map to 'AdministrativeArea2'.


    Args:
        parent_place_name: The name of the parent geographic area (e.g., 'Kenya').
        child_place_types: The canonical child place types to check for (e.g., 'AdministrativeArea1').

    Returns:
        A dictionary mapping child place types to a boolean indicating whether they are valid for the parent place.
    """
    places = await multi_dc_client.base_dc.search_places([parent_place_name])
    place_dcid = places.get(parent_place_name, "")
    if not place_dcid:
        return dict.fromkeys(child_place_types, False)

    tasks = [
        multi_dc_client.base_dc.child_place_type_exists(
            place_dcid,
            child_place_type,
        )
        for child_place_type in child_place_types
    ]

    results = await asyncio.gather(*tasks)

    return dict(zip(child_place_types, results, strict=False))


@mcp.tool()
async def get_available_variables(
    place_name: str = "world", category: str = "statistics"
) -> dict:
    """
    Gets available variables for a place and category.
    If a place is not specified, it returns variables for the world.
    If not specified, it returns variables for a generic category called "statistics".

    Use this tool to discover what statistical data is available for a particular geographic area and category.

    Args:
        place_name (str): The name of the place to fetch variables for. e.g. "United States", "India", "NYC", etc.
        category (str): The category of variables to fetch. e.g. "Demographics", "Economy", "Health", "Education", "Environment", "Women With Arthritis by Age", etc.

    Returns:
        A dictionary containing the status of the request and the data if available.

        The data will have the following format:
        {
          "status": "SUCCESS",
          "data": {
            "place_dcid": str,
            "category_variable_ids": list[str],
            "id_name_mappings": dict
          }
        }

        In your response, use the id_name_mappings to convert the variable and place dcids to human-readable names.

        You can use the category_variable_ids to get the variables in the requested category (or for "statistics" by default).

        If the user asks to see the data for this category and there are a high number of variables, pick those most pertinent to the user's query and context.
        When showing this info to the user, inform them of the total number of variables available *for this specific place and category* (e.g., 'statistics for the world')
        and the variables for that combination.

        **Crucially**, categorize the variables into categories as appropriate (e.g. "Demographics", "Economy", "Health", "Education", "Environment", etc.) to make the information easier to digest.

        Typically this tool is called when the user asks to see the data for a specific category for a given place.

        It can also be called for a general "what data do you have".
        In this case we'll return generic statistics data for the world.
        For this general case, emphasize that these are variables available for just this combination.
        The overall collection of variables and datasets is much larger.
        You can then prompt the user to ask a specific question about the data and
        possibly suggest a few questions to ask.

        Most importantly, in all cases, categorize the variables as mentioned above when displaying them to the user.
    """
    places = await multi_dc_client.base_dc.search_places([place_name])
    place_dcid = places.get(place_name)

    if not place_dcid:
        return {
            "status": "NOT_FOUND",
            "message": f"Could not find a place named '{place_name}'.",
        }

    dc = multi_dc_client.base_dc
    variable_data = await dc.fetch_topic_variables(place_dcid, topic_query=category)

    dcids_to_lookup = [place_dcid]

    topic_variable_ids = variable_data.get("topic_variable_ids", [])
    dcids_to_lookup.extend(topic_variable_ids)

    id_name_mappings = dc.fetch_entity_names(dcids_to_lookup)

    return {
        "status": "SUCCESS",
        "data": {
            "place_dcid": place_dcid,
            "topic_variable_ids": topic_variable_ids,
            "id_name_mappings": id_name_mappings,
        },
    }


@mcp.tool()
async def get_datacommons_chart_config(
    chart_type: str,
    chart_title: str,
    variable_dcids: list[str],
    place_dcids: list[str] | None = None,
    parent_place_dcid: str | None = None,
    child_place_type: str | None = None,
) -> DataCommonsChartConfig:
    """Constructs and validates a DataCommons chart configuration.

    This unified factory function serves as a robust constructor for creating
    any type of DataCommons chart configuration from primitive inputs. It uses a
    dispatch map to select the appropriate Pydantic model based on the provided
    `chart_type` and validates the inputs against that model's rules.

    **Crucially** use the DCIDs of variables, places and/or child place types
    returned by other tools as the args to the chart config.

    Valid chart types include:
     - line: accepts multiple variables and either location specification
     - bar: accepts multiple variables and either location specification
     - pie: accepts multiple variables for a single place_dcid
     - map: accepts a single variable for a parent-child spec
        - a heat map based on the provided statistical variable
     - highlight: accepts a single variable and single place_dcid
        - displays a single statistical value for a given place in a nice format
     - ranking: accepts multiple variables for a parent-child spec
        - displays a list of places ranked by the provided statistical variable
     - gauge: accepts a single variable and a single place_dcid
        - displays a single value on a scale range from 0 to 100

    The function supports two mutually exclusive methods for specifying location:
    1. By a specific list of places via `place_dcids`.
    2. By a parent-child relationship via `parent_place_dcid` and
        `child_place_type`.

    Prefer supplying a parent-child relationship pair over a long list of dcids
    where appilicable. If there is an error, it may be worth trying the other
    location option (ie if there is an error with generating a config for a place-dcid
    list, try again with a parent-child relationship if it's relevant).

    It handles all validation internally and returns a strongly-typed Pydantic
    object, ensuring that any downstream consumer receives a valid and complete
    chart configuration.

    Args:
        chart_type: The key for the desired chart type (e.g., "bar", "scatter").
            This determines the required structure and validation rules.
        chart_title: The title to be displayed on the chart header.
        variable_dcids: A list of Data Commons Statistical Variable DCIDs.
            Note: For charts that only accept a single variable, only the first
            element of this list will be used.
        place_dcids: An optional list of specific Data Commons Place DCIDs. Use
            this for charts that operate on one or more enumerated places.
            Cannot be used with `parent_place_dcid` or `child_place_type`.
        parent_place_dcid: An optional DCID for a parent geographical entity.
            Use this for hierarchy-based charts. Must be provided along with
            `child_place_type`.
        child_place_type: An optional entity type for child places (e.g.,
            "County", "City"). Use this for hierarchy-based charts. Must be
            provided along with `parent_place_dcid`.

    Returns:
        A validated Pydantic object representing the complete chart
        configuration. The specific class of the object (e.g., BarChartConfig,
        ScatterChartConfig) is determined by the `chart_type`.

    Raises:
        ValueError:
            - If `chart_type` is not a valid, recognized chart type.
            - If `variable_dcids` is an empty list.
            - If no location information is provided at all.
            - If both `place_dcids` and hierarchy parameters are provided.
            - If the provided location parameters are incompatible with the
              requirements of the specified `chart_type` (e.g., providing
              `place_dcids` for a chart that requires a hierarchy).
            - If any inputs fail Pydantic's model validation for the target
              chart configuration.
    """
    # Validate chart_type param
    chart_config_class = CHART_CONFIG_MAP.get(chart_type)
    if not chart_config_class:
        raise ValueError(
            f"Invalid chart_type: '{chart_type}'. Valid types are: {list(CHART_CONFIG_MAP.keys())}"
        )

    # Validate provided place params
    if not place_dcids and not (parent_place_dcid and child_place_type):
        raise ValueError(
            "Supply either a list of place_dcids or a single parent_dcid-child_place_type pair."
        )
    if place_dcids and (parent_place_dcid or child_place_type):
        raise ValueError(
            "Provide either 'place_dcids' or a 'parent_dcid'/'child_place_type' pair, but not both."
        )

    # Validate variable params
    if not variable_dcids:
        raise ValueError("At least one variable_dcid is required.")

    # 2. Intelligently construct the location object based on the input
    #    This part makes some assumptions based on the provided signature.
    #    For single-place charts, we use the first DCID. For multi-place, we use all.
    try:
        location_model = chart_config_class.model_fields["location"].annotation
        location_obj = None

        # Check if the annotation is a Union (e.g., Union[A, B] or A | B)
        if get_origin(location_model) in (Union, types.UnionType):
            # Get the types inside the Union
            # e.g., (SinglePlaceLocation, MultiPlaceLocation)
            possible_location_types = get_args(location_model)
        else:
            possible_location_types = [location_model]

        # Now, check if our desired types are possible options
        if MultiPlaceLocation in possible_location_types and place_dcids:
            # Prioritize MultiPlaceLocation if multiple places are given
            location_obj = MultiPlaceLocation(place_dcids=place_dcids)
        elif SinglePlaceLocation in possible_location_types and place_dcids:
            # Fall back to SinglePlaceLocation if it's an option
            location_obj = SinglePlaceLocation(place_dcid=place_dcids[0])
        elif HierarchyLocation in possible_location_types and (
            parent_place_dcid and child_place_type
        ):
            location_obj = HierarchyLocation(
                parent_place_dcid=parent_place_dcid, child_place_type=child_place_type
            )
        else:
            # The Union doesn't contain a type we can build
            raise ValueError(
                f"Chart type '{chart_type}' requires a location type "
                f"('{location_model.__name__}') that this function cannot build from "
                "the provided args."
            )

        if issubclass(chart_config_class, SingleVariableChart):
            return chart_config_class(
                header=chart_title,
                location=location_obj,
                variable_dcid=variable_dcids[0],
            )

        return chart_config_class(
            header=chart_title, location=location_obj, variable_dcids=variable_dcids
        )

    except ValidationError as e:
        # Catch Pydantic errors and make them more user-friendly
        raise ValueError(f"Validation failed for chart_type '{chart_type}': {e}") from e


@mcp.tool()
async def search_topics_and_variables(
    query: str,
    place1_name: str | None = None,
    place2_name: str | None = None,
) -> dict:
    """Search for topics and variables (collectively called "indicators") across Data Commons.

    This tool returns candidate indicators that match your query. You should treat these as
    candidates and filter them based on the user's query and context to surface the most
    relevant results.

    **How to Use This Tool:**

    * **For place-constrained queries** like "basic health grants to Bolivia":
        - Call with `query="basic health grants"` and `place1_name="Bolivia"`
        - The tool will match indicators and perform existence checks for the specified place

    * **For bilateral place-constrained queries** like "basic health grants from France to Bolivia":
        - Call with `query="basic health grants"`, `place1_name="France"`, and `place2_name="Bolivia"`
        - The tool will match indicators and perform existence checks for both places
        - In bilateral data, one place (e.g., "France") is encoded in the variable name, while the other place (e.g., "Bolivia") is where we have observations
        - Use `places_with_data` to identify which place has observations.

    * **For non-place-constrained queries** like "what basic health data do you have":
        - Call with just the `query` parameter
        - No place existence checks are performed

    Args:
        query (str): The search query for indicators (topics, categories, or variables).
            Examples: "health grants", "carbon emissions", "unemployment rate"
        place1_name (str, optional): First place name for filtering and existence checks.
            Examples: "France", "United States", "California"
        place2_name (str, optional): Second place name for filtering and existence checks.
            Examples: "Albania", "Germany", "New York"

    Returns:
        dict: A dictionary containing candidate indicators with the following structure:
            {
                "topics": [
                    {
                        "dcid": str,  # Topic DCID
                        "member_topics": list[str],  # Direct member topic DCIDs
                        "member_variables": list[str],  # Direct member variable DCIDs
                        "places_with_data": list[str]  # Place DCIDs where data exists (only if place filtering was performed)
                    }
                ],
                "variables": [
                    {
                        "dcid": str,  # Variable DCID
                        "places_with_data": list[str]  # Place DCIDs where data exists (only if place filtering was performed)
                    }
                ],
                "lookups": dict[str, str]  # DCID to name mappings
            }

    **Processing the Response:**
    * **Topics**: Collections of variables and sub-topics. Use the lookups to get readable names.
    * **Variables**: Individual data indicators. Use the lookups to get readable names.
    * **places_with_data**: Only present when place filtering was performed. Shows which requested places have data for each indicator.
    * **Filter and rank**: Treat all results as candidates and filter/rank based on user context.
    * **Data availability**: Use `places_with_data` to understand which places have data for each indicator.
    """
    return await _search_topics_and_variables_impl(query, place1_name, place2_name)


async def _search_topics_and_variables_impl(
    query: str, place1_name: str | None = None, place2_name: str | None = None
) -> dict:
    """Implementation of search_topics_and_variables tool."""
    
    # Resolve all place names to DCIDs in a single call
    place_names = [name for name in [place1_name, place2_name] if name]
    place_dcids_map = {}
    
    if place_names:
        try:
            place_dcids_map = await multi_dc_client.base_dc.search_places(place_names)
        except Exception:
            # If place resolution fails, continue with empty map (not an error)
            pass
    
    place1_dcid = place_dcids_map.get(place1_name) if place1_name else None
    place2_dcid = place_dcids_map.get(place2_name) if place2_name else None
    
    # Construct search queries with their corresponding place DCIDs for filtering
    search_tasks = []
    
    # Base query: search for the original query, filter by all available places
    base_place_dcids = []
    if place1_dcid:
        base_place_dcids.append(place1_dcid)
    if place2_dcid:
        base_place_dcids.append(place2_dcid)
    
    search_tasks.append((query, base_place_dcids))
    
    # Place1 query: search for query + place1_name, filter by place2_dcid
    if place1_dcid:
        place1_place_dcids = [place2_dcid] if place2_dcid else []
        search_tasks.append((f"{query} {place1_name}", place1_place_dcids))
    
    # Place2 query: search for query + place2_name, filter by place1_dcid
    if place2_dcid:
        place2_place_dcids = [place1_dcid] if place1_dcid else []
        search_tasks.append((f"{query} {place2_name}", place2_place_dcids))
    
    # Execute parallel searches
    tasks = []
    for search_query, place_dcids in search_tasks:
        task = multi_dc_client.fetch_topics_and_variables(
            search_query, place_dcids=place_dcids, max_results=10
        )
        tasks.append(task)
    
    # Wait for all searches to complete
    results = await asyncio.gather(*tasks)
    
    # Merge and deduplicate results
    # Filter out None place DCIDs
    valid_place_dcids = [dcid for dcid in [place1_dcid, place2_dcid] if dcid is not None]
    merged_result = await _merge_search_results(results, valid_place_dcids)
    
    return merged_result


def _collect_all_dcids(topics: list[dict], variables: list[str], place_dcids: list[str] = None) -> list[str]:
    """Collect all DCIDs from topics, variables, and places."""
    all_dcids = set()
    
    # Collect topic DCIDs and their member DCIDs
    for topic in topics:
        all_dcids.add(topic["dcid"])
        # Handle member_topics - could be strings or dicts
        member_topics = topic.get("member_topics", [])
        for member in member_topics:
            if isinstance(member, dict):
                all_dcids.add(member["dcid"])
            else:
                all_dcids.add(member)
        # Handle member_variables - could be strings or dicts
        member_variables = topic.get("member_variables", [])
        for member in member_variables:
            if isinstance(member, dict):
                all_dcids.add(member["dcid"])
            else:
                all_dcids.add(member)
    
    # Collect variable DCIDs
    all_dcids.update(variables)
    
    # Collect place DCIDs if provided
    if place_dcids:
        all_dcids.update(place_dcids)
    
    # Filter out None values and empty strings
    result = [dcid for dcid in all_dcids if dcid is not None and dcid.strip()]
    return result


async def _fetch_and_update_lookups(dcids: list[str]) -> dict:
    """Fetch names for all DCIDs and return as lookups dictionary."""
    if not dcids:
        return {}
    
    try:
        result = multi_dc_client.fetch_entity_names(dcids)
        return result
    except Exception:
        # If fetching fails, return empty dict (not an error)
        return {}


async def _merge_search_results(results: list[dict], place_dcids: list[str] = None) -> dict:
    """Union results from multiple search calls."""
    
    # Collect all topics and variables
    all_topics = {}
    all_variables = {}
    
    for result in results:
        # Union topics
        for topic in result.get("topics", []):
            topic_dcid = topic["dcid"]
            if topic_dcid not in all_topics:
                all_topics[topic_dcid] = topic
        
        # Union variables
        for variable in result.get("variables", []):
            var_dcid = variable["dcid"]
            if var_dcid not in all_variables:
                all_variables[var_dcid] = variable
    
    # Collect all DCIDs and fetch their names
    all_dcids = _collect_all_dcids(
        list(all_topics.values()), 
        list(all_variables.keys()), 
        place_dcids
    )
    
    # Fetch names for all DCIDs and use as lookups
    lookups = await _fetch_and_update_lookups(all_dcids)
    
    return {
        "topics": list(all_topics.values()),
        "variables": list(all_variables.values()),
        "lookups": lookups,
    }
