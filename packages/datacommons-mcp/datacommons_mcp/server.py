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
import logging
import types
from typing import Union, get_args, get_origin

from fastmcp import FastMCP
from pydantic import ValidationError

import datacommons_mcp.settings as settings
from datacommons_mcp.clients import create_dc_client
from datacommons_mcp.data_models.charts import (
    CHART_CONFIG_MAP,
    DataCommonsChartConfig,
    HierarchyLocation,
    MultiPlaceLocation,
    SinglePlaceLocation,
    SingleVariableChart,
)
from datacommons_mcp.data_models.observations import (
    ObservationToolResponse,
)
from datacommons_mcp.data_models.search import (
    SearchResponse,
    SearchTopic,
    SearchVariable,
)
from datacommons_mcp.services import (
    get_observations as get_observations_service,
    search_indicators as search_indicators_service,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create client based on settings
try:
    dc_settings = settings.get_dc_settings()
    logger.info("Loaded DC settings:\n%s", dc_settings.model_dump_json(indent=2))
    dc_client = create_dc_client(dc_settings)
except ValidationError as e:
    logger.error("Settings error: %s", e)
    raise
except Exception as e:
    logger.error("Failed to create DC client: %s", e)
    raise

mcp = FastMCP("DC MCP Server")


@mcp.tool()
async def get_observations(
    variable_dcid: str,
    place_dcid: str | None = None,
    place_name: str | None = None,
    child_place_type: str | None = None,
    source_id_override: str | None = None,
    period: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ObservationToolResponse:
    """Fetches observations for a statistical variable from Data Commons.

    This tool can operate in two primary modes:
    1.  **Single Place Mode**: Get data for one specific place (e.g., "Population of California").
    2.  **Child Places Mode**: Get data for all child places of a certain type within a parent place (e.g., "Population of all counties in California").

    ### Core Logic & Rules

    * **Variable Selection**: You **must** provide the `variable_dcid`.
        * Variable DCIDs are unique identifiers for statistical variables in Data Commons and are returned by prior calls to the
        `search_indicators` tool.

    * **Place Selection**: You **must** provide either `place_dcid` or `place_name`.
        * If `place_dcid` is provided, it takes priority over `place_name`.
        * **Important Note for Bilateral Data**: When fetching data for bilateral variables (e.g., exports from one country to another),
        the `variable_dcid` often encodes one of the places (e.g., `TradeExports_FRA` refers to exports *to* France).
        In such cases, the `place_dcid` (or `place_name`) parameter in `get_observations` should specify the *other* place involved in the bilateral relationship
        (e.g., the exporter country, such as 'USA' for exports *from* USA).
        The `search_indicators` tool's `places_with_data` field can help identify which place is the appropriate observation source for `place_dcid` (or `place_name`).

    * **Mode Selection**:
        * To get data for the specified place (e.g., California), **do not** provide `child_place_type`.
        * To get data for all its children (e.g., all counties in California), you **must also** provide the `child_place_type` (e.g., "County"). Use the `validate_child_place_types` tool to find valid types.
          **CRITICAL:** Before calling `get_observations` with `child_place_type`, you **MUST** first call the `validate_child_place_types` tool to find valid types.
          Only proceed with `get_observations` if `validate_child_place_types` confirms that the `child_place_type` is valid for the specified parent place.

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
      variable_dcid (str, required): The unique identifier (DCID) of the statistical variable.
      place_dcid (str, optional): The DCID of the place.
      place_name (str, optional): The common name of the place. Ex: "United States", "India", "NYC". Ignored if `place_dcid` is set.
      child_place_type (str, optional): The type of child places to get data for. **Use this to switch to Child Places Mode.**
      source_id_override (str, optional): An optional facet ID to force the use of a specific data source.
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
    return await get_observations_service(
        client=dc_client,
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        place_name=place_name,
        child_place_type=child_place_type,
        source_id_override=source_id_override,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )


@mcp.tool()
async def validate_child_place_types(
    parent_place_name: str, child_place_types: list[str]
) -> dict[str, bool]:
    """
    Checks which of the child place types are valid for the parent place.

    Use this tool to validate the child place types before calling get_observations for those places.

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
    places = await dc_client.search_places([parent_place_name])
    place_dcid = places.get(parent_place_name, "")
    if not place_dcid:
        return dict.fromkeys(child_place_types, False)

    tasks = [
        dc_client.child_place_type_exists(
            place_dcid,
            child_place_type,
        )
        for child_place_type in child_place_types
    ]

    results = await asyncio.gather(*tasks)

    return dict(zip(child_place_types, results, strict=False))


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
async def search_indicators(
    query: str,
    places: list[str] | None = None,
    include_topics: bool = True,
    maybe_bilateral: bool = False,
    per_search_limit: int = 10,
) -> SearchResponse:
    """Search for topics and variables (collectively called "indicators") across Data Commons.

    This tool returns candidate indicators that match your query. You should treat these as
    candidates and filter them based on the user's query and context to surface the most
    relevant results.


    **How to Use This Tool:**

    * **For place-constrained queries** like "population of France":
        - Call with `query="population"`, `places=["France"]`, and `maybe_bilateral=False`
        - The tool will match indicators and perform existence checks for the specified place

    * **For place-constrained queries** where the agent deems the indicator *could* represent a bilateral relationship like "trade exports to France":
        - Call with `query="trade exports"`, `places=["France"]`, and `maybe_bilateral=True`
        - The tool will match indicators and perform existence checks for the specified place

    * **For bilateral place-constrained queries**:
        - between two places like "trade exports from USA to France":
          + Call with `query="trade exports"`, `places=["USA", "France"]`, and `maybe_bilateral=True`
        - between multiple places like "trade exports from USA, Germany and UK to France":
          + Call with `query="trade exports"`, `places=["USA", "Germany", "UK", "France"]`, and `maybe_bilateral=True`
        - The tool will match indicators and perform existence checks for the specified places
        - In bilateral data, one place (e.g., "France") is encoded in the variable name, while
          the other place (e.g., "USA", "Germany", "UK") is where we have observations
        - Use `places_with_data` to identify which place has observations

    * **For child entity sampling** like "population of Indian states":
        - Call with `query="population"` and `places=["Uttar Pradesh", "Maharashtra", "Tripura", "Bihar", "Kerala"]`
        - Sample 5-6 diverse child entities as representative proxy for all child entities
        - Results are indicative of broader child entity coverage

    * **For exploratory queries** like "what basic health data do you have":
        - Call with `query="basic health"`
        - The tool will return organized topic categories and variables

    * **For non-place-constrained queries** like "what trade data do you have":
        - Call with `query="trade"`
        - No place existence checks are performed

    Args:
        query (str): The search query for indicators (topics, categories, or variables).
            Examples: "health grants", "carbon emissions", "unemployment rate", "share of government spending on health"
        places (list[str], optional): List of place names for filtering and existence checks.
            Examples: ["USA"], ["USA", "Canada"], ["Uttar Pradesh", "Maharashtra", "Tripura", "Bihar", "Kerala"]
        include_topics (bool, optional): Whether to search for Topics (collections of variables) or
            just variables. Default: True
        maybe_bilateral (bool, optional): Whether this query could represent bilateral relationships.
            Set to True for queries which may involve more than one entity/place (e.g., `to` or `from`
            like trade between countries, aid to a country, loans from an entity to another)
            Set to False for queries about properties of places (e.g., "population of france").
            Default: False
        per_search_limit (int, optional): Maximum results per search (default 10, max 100). A single query may trigger multiple internal searches.

    Returns:
        dict: A dictionary containing candidate indicators with the following structure:
            {
                "topics": [ # Only if `include_topics` is True
                    {
                        "dcid": str,  # Topic DCID
                        "member_topics": list[str],  # Direct member topic DCIDs
                        "member_variables": list[str],  # Direct member variable DCIDs
                        "places_with_data": list[str]  # Place DCIDs where data exists (if place filtering was performed)
                    }
                ],
                "variables": [
                    {
                        "dcid": str,  # Variable DCID
                        "places_with_data": list[str]  # Place DCIDs where data exists (if place filtering was performed)
                    }
                ],
                "dcid_name_mappings": dict[str, str],  # DCID to name mappings
                "status": str  # Status of the search operation
            }

        **If `include_topics = True`**: Returns both topics and variables with hierarchical structure
        **If `include_topics = False`**: Returns only variables

    **Processing the Response:**
    * **Topics**: Collections of variables and sub-topics. Use the dcid_name_mappings to get readable names.
    * **Variables**: Individual data indicators. Use the dcid_name_mappings to get readable names.
    * **places_with_data**: Only present when place filtering was performed. Shows which requested places have data for each indicator.
    * **Filter and rank**: Treat all results as candidates and filter/rank based on user context.
    * **Data availability**: Use `places_with_data` to understand which places have data for each indicator.

    **Best Practices:**
    - Include topics if you want to understand data organization and discover collections of variables (topics) or related variables
    - Exclude topics only when you have a specific query for a precise variable.
    - For child entity queries, sample 5-6 diverse child entities as representative proxy
    """
    # Call the real search_indicators service
    return await search_indicators_service(
        client=dc_client,
        query=query,
        places=places,
        maybe_bilateral=maybe_bilateral,
        per_search_limit=per_search_limit,
    )
