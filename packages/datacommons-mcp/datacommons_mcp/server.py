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
    ObservationDateType,
    ObservationToolResponse,
)
from datacommons_mcp.data_models.search import (
    SearchResponse,
)
from datacommons_mcp.services import (
    get_observations as get_observations_service,
)
from datacommons_mcp.services import (
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

mcp = FastMCP(
    "DC MCP Server",
    stateless_http=True,
)


@mcp.tool()
async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    child_place_type: str | None = None,
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> ObservationToolResponse:
    """Fetches observations for a statistical variable from Data Commons.

    **CRITICAL: Always validate variable-place combinations first**
    - You **MUST** call `search_indicators` first to verify that the variable exists for the specified place
    - Only use DCIDs returned by `search_indicators` - never guess or assume variable-place combinations
    - This ensures data availability and prevents errors from invalid combinations

    This tool can operate in two primary modes:
    1.  **Single Place Mode**: Get data for one specific place (e.g., "Population of California").
    2.  **Child Places Mode**: Get data for all child places of a certain type within a parent place (e.g., "Population of all counties in California").

    ### Core Logic & Rules

    * **Variable Selection**: You **must** provide the `variable_dcid`.
        * Variable DCIDs are unique identifiers for statistical variables in Data Commons and are returned by prior calls to the
        `search_indicators` tool.

    * **Place Selection**: You **must** provide the `place_dcid`.
        * **Important Note for Bilateral Data**: When fetching data for bilateral variables (e.g., exports from one country to another),
        the `variable_dcid` often encodes one of the places (e.g., `TradeExports_FRA` refers to exports *to* France).
        In such cases, the `place_dcid` parameter in `get_observations` should specify the *other* place involved in the bilateral relationship
        (e.g., the exporter country, such as 'USA' for exports *from* USA).
        The `search_indicators` tool's `places_with_data` field can help identify which place is the appropriate observation source for `place_dcid`.

    * **Mode Selection**:
        * To get data for the specified place (e.g., California), **do not** provide `child_place_type`.
        * To get data for all its children (e.g., all counties in California), you **must also** provide the `child_place_type` (e.g., "County").
          **CRITICAL:** Before calling `get_observations` with `child_place_type`, you **MUST** first call `search_indicators` with child sampling to determine the correct child place type.
          **Child Type Determination Logic:**
          1. Use the `dcid_place_type_mappings` field from the `search_indicators` response to examine the types of sampled child places
          2. Use the type that is common to ALL sampled child places
          3. If more than one type is common to all child places, use the most specific type
          4. If there is no common type across all sampled child places, use the majority type (50%+ threshold) if there's a clear majority
          5. If there is no common type and no clear majority, child `get_observations` calls cannot be made - fall back to individual non-child `get_observations` calls for each place
          **Note:** If you used child sampling in `search_indicators` to validate variable existence, you should still get data for ALL children of that type, not just the sampled subset.

    * **Data Volume Constraint**: When using **Child Places Mode** (when `child_place_type` is set), you **must** be conservative with your date range to avoid requesting too much data.
        * Avoid requesting `'all'` data via the `date` parameter.
        * **Instead, you must either request the `'latest'` data or provide a specific, bounded date range.**

    * **Date Filtering**: The tool filters observations by date using the following priority:
        1.  **`date`**: The `date` parameter is required and can be one of the enum values 'all', 'latest', 'range', or a date string in the format 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'.
        2.  **Date Range**: If `date` is set to 'range', you must specify a date range using `date_range_start` and/or `date_range_end`.
            * If only `date_range_start` is specified, then the response will contain all observations starting at and after that date (inclusive).
            * If only `date_range_end` is specified, then the response will contain all observations before and up to that date (inclusive).
            * If both are specified, the response contains observations within the provided range (inclusive).
            * Dates must be in `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` format.
        3.  **Default Behavior**: If you do not provide **any** date parameters (`date`, `date_range_start`, or `date_range_end`), the tool will automatically fetch only the `'latest'` observation.

    Args:
      variable_dcid (str, required): The unique identifier (DCID) of the statistical variable.
      place_dcid (str, required): The DCID of the place.
      child_place_type (str, optional): The type of child places to get data for. **Use this to switch to Child Places Mode.**
      source_override (str, optional): An optional source ID to force the use of a specific data source.
      date (str, optional): An optional date filter. Accepts 'all', 'latest', 'range', or single date values of the format 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'. Defaults to 'latest' if no date parameters are provided.
      date_range_start (str, optional): The start date for a range (inclusive). **Used only if `date` is set to'range'.**
      date_range_end (str, optional): The end date for a range (inclusive). **Used only if `date` is set to'range'.**

    Returns:
        The fetched observation data including:
        - `variable`: Details about the statistical variable requested.
        - `place_observations`: A list of observations, one entry per place. Each entry contains:
            - `place`: Details about the observed place (DCID, name, type).
            - `time_series`: A list of `(date, value)` tuples, where `date` is a string (e.g., "2022-01-01") and `value` is a float.
        - `source_metadata`: Information about the primary data source used.
        - `alternative_sources`: Details about other available data sources.

    """
    # TODO(keyurs): Remove place_name parameter from the service call.
    return await get_observations_service(
        client=dc_client,
        variable_dcid=variable_dcid,
        place_dcid=place_dcid,
        place_name=None,
        child_place_type=child_place_type,
        source_override=source_override,
        date=date,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )


# TODO(clincoln8): Add to optional visualization toolset
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
    per_search_limit: int = 10,
    *,
    include_topics: bool = True,
    maybe_bilateral: bool = False,
) -> SearchResponse:
    """
    **Purpose:**
    Search for topics and variables (collectively called "indicators") available in the Data Commons Knowledge Graph.

    **Core Concept: Results are Candidates**
    This tool returns *candidate* indicators that match your query. You must always filter and rank these results based on the user's context to find the most relevant one.

    **Background: Data Commons Structure**
    Data Commons organizes data in two main hierarchies:

    1. **Topics:** A hierarchy of categories (e.g., `Health` -> `Clinical Data` -> `Medical Conditions`). Topics contain sub-topics and member variables.

    2. **Places:** A hierarchy of geographic containment (e.g., `World` -> `Continent` -> `Country` -> `State`).

    **CRITICAL DATA PRINCIPLE:**
    The *same* statistical concept (e.g., "Population") might use *different* indicator DCIDs for different place types (e.g., one DCID for `Country` and another for `State`). This tool is essential for discovering *which* specific indicators are available for the `places` you are querying.

    **Efficiency Tips:**

    * Data coverage is generally high at the `Country` level.

    * Fetching direct children of a place (e.g., states in a country) is efficient.

    ### Parameters

    **1. `query` (str, required)**

      - The search query for indicators (topics or variables).

      - **Examples:** `"health grants"`, `"carbon emissions"`, `"unemployment rate"`

      - **CRITICAL RULES:**
        * Search for one concept at a time to get focused results.
          - Instead of: "health and unemployment rate" (single search)
          - Use: "health" and "unemployment rate" as separate searches

    **2. `places` (list[str], optional)**

      - A list of English, human-readable place names to filter indicators by.

      - If provided, the tool will only return indicators that have data for at least one of the specified places.

      - **CRITICAL RULES:**

        - **ALWAYS qualify place names** with geographic context to avoid ambiguity (e.g., `"California, USA"`, `"Paris, France"`, `"Springfield, IL"`).

        - **ALWAYS specify administrative level** when ambiguous For instance:
    5     - For the city: `"Madrid, Spain"`
    6     - For the autonomous community: `"Community of Madrid, Spain"`
    7     - Similarly, differentiate between `"New York City, USA"` and `"New York State, USA"`.

        - **ALWAYS** use qualified, readable names (e.g., `"California, USA"`, `"Canada"`, `"World"`).

        - **NEVER** use DCIDs (e.g., `"geoId/06"`, `"country/CAN"`).

        - If you get place info from another tool, extract and use *only* the readable name, but always qualify it with geographic context.

        - **CRITICAL:** Always qualify place names to avoid ambiguity (e.g., `"Scotland, UK"` not `"Scotland"`, `"California, USA"` not `"California"`).

      **Place Name Qualification Guidelines:**

      - **Geographic Disambiguation:** Add country/region context (e.g., `"Scotland, UK"` vs `"Scotland County, USA"`)
      - **Administrative Level Disambiguation:** Specify city vs state vs country level (e.g., `"New York City, USA"` vs `"New York State, USA"`)
      - **Common Ambiguous Cases:**
        - **New York:** `"New York City, USA"` vs `"New York State, USA"`
        - **Madrid:** `"Madrid, Spain"` (city) vs `"Community of Madrid, Spain"`
        - **London:** `"London, UK"` (city) vs `"London, Ontario, Canada"`
        - **Washington:** `"Washington, DC, USA"` vs `"Washington State, USA"`
        - **Springfield:** `"Springfield, IL, USA"` vs `"Springfield, MO, USA"` (add state)

      - When searching for indicators related to child places within a larger geographic entity (e.g., states within a country, or countries within a continent/the world), you MUST include the parent entity and a diverse sample of 5-6 of its child places in the `places` list.
       This ensures the discovery of indicators that have data at the child place level. Refer to 'Recipe 4: Sampling Child Places' for detailed examples.

      **How to Use the `places` Parameter (Recipes):**

      - **Recipe 1: Data for a Specific Place**

        - **Goal:** Find an indicator *about* a single place (e.g., "population of France").

        - **Call:** `query="population"`, `places=["France"]`, `maybe_bilateral=False`

      - **Recipe 2: Sampling Child Places**

        - **Goal:** Check data availability for a *type* of child place (e.g., "population of Indian states" or "highest GDP countries" or "top 5 US states with lowest unemployment rate").

        - **Action:** You must *proxy* this request by sampling a few children.

        - **Example 1: Child places of a country**
          - **Call:**
            * `query="population"`
            * `places=["India", "Uttar Pradesh, India", "Maharashtra, India", "Tripura, India", "Bihar, India", "Kerala, India"]`
          - **Logic:**
            1. Include the parent ("India") to find parent-level indicators.
            2. Include 5-6 *diverse* child places (e.g., try to pick large/small, north/south/east/west, if known).
            3. The results for these 5-6 places are a *proxy* for all children.
            4. If a sampled child place shows data for an indicator, assume that data is available for all child places of that type for that indicator.
                Conversely, if, after sampling, no child place shows data for a specific indicator, assume that data is not available for any of the child places
                for that indicator.

        - **Example 2: Child places of the World (Countries)**
          - **Call:**
            * `query="GDP"`
            * `places=["World", "USA", "China", "Germany", "Nigeria", "Brazil"]`
          - **Logic:**
            1. Include the parent ("World").
            2. Include 5-6 *diverse* child countries (e.g., from different continents, different economies).
            3. This sampling helps discover the correct indicator DCID used for the `Country` place type, which you can then use in other tools (like `fetch_data` with a parent=`World` and child_type=`Country`).

        - **Example 3: Administrative Level Sampling**

          - **Goal:** Check data availability for different administrative levels (e.g., "population of US cities" vs "population of US states").

          - **Call:**
            * **For Cities:** `query="population"`, `places=["USA", "New York City, USA", "Los Angeles, USA", "Chicago, USA", "Houston, USA", "Phoenix, USA"]`
            * **For States:** `query="population"`, `places=["USA", "California, USA", "Texas, USA", "Florida, USA", "New York State, USA", "Pennsylvania, USA"]`
          - **Logic:** Specify the exact administrative level you want to sample to avoid confusion between city and state data.

      - **Recipe 3: Potentially Bilateral Data**

        - **Goal:** Find an indicator that *might* be bilateral (e.g., "trade exports to France"). The data might be *about* France, or it might be *from* other places *to* France.

        - **Call:** `query="trade exports"`, `places=["France"]`, `maybe_bilateral=True`

      - **Recipe 4: Known Bilateral Data (Multi-Place)**

        - **Goal:** Find data *between* places (e.g., "trade from USA and Germany to France").

        - **Call:** `query="trade exports"`, `places=["USA", "Germany", "France"]`, `maybe_bilateral=True`

        - **Note:** The response's `places_with_data` will show which of "USA", "Germany", or "France" the observations are attached to. The other places are often part of the variable name itself.

      - **Recipe 5: No Place Filtering**

        - **Goal:** Find indicators for a query without checking any specific place (e.g., "what trade data do you have").

        - **Call:** `query="trade"`. Do not set `places`.

        - **Result:** The tool returns matching indicators, but `places_with_data` will be empty.

    **3. `per_search_limit` (int, optional, default=10, max=100)**

      - Maximum results per search.

      - **CRITICAL RULE:** Only set per_search_limit when explicitly requested by the user.
        - Use the default value (10) unless the user specifies a different limit
        - Don't assume the user wants more or fewer results

    **4. `include_topics` (bool, optional, default=True)**

      - **Primary Rule:** If a user explicitly states what they want, follow their request. Otherwise, use these guidelines:

      - **`include_topics = True` (Default): For Exploration & Discovery**

        - **Purpose:** To explore the data hierarchy and find related variables.

        - **Use when:**

          - The user is exploring (e.g., "what basic health data do you have?").

          - You need to understand how data is organized to ask a better follow-up.

       - **Returns:** Both topics (categories) and variables.

      - **`include_topics = False`: For Specific Data**

        - **Purpose:** To find a specific variable for fetching data.

        - **Use when:**

          - The user's goal is to get a specific number or dataset (e.g., "find unemployment rate for United States").

        - **Returns:** Variables only.

    **5. `maybe_bilateral` (bool, optional, default=False)**

      - Set to `True` if the query implies a relationship *between* places (e.g., "trade", "migration", "exports to France").

      - Set to `False` (default) for queries about a *property of* a place (e.g., "population", "unemployment rate", "carbon emissions in NYC").

      - See the "Recipes" in the `places` parameter section for specific examples.

    ### Special Query Scenarios

    **Scenario 1: Vague, Unqualified Queries ("what data do you have?")**
      - **Action:** If a user asks a general question about available data, proactively call the tool for "World" to provide an initial overview.

      - **Call:** `query=""`, `places=["World"]`, `include_topics=True`

      - **Result:** This returns the top-level topics for the World.

      - **Agent Follow-up:** After showing the World data, consider asking if the user would like to see data for a different, more specific place if it seems helpful for the conversation.

      - **Example agent response:** "Here is a general overview of the data topics available for the World. You can also ask for this information for a specific place, like 'Africa', 'India', 'California, USA', or 'Paris, France'."

    **Scenario 2: Ambiguous Place Names**

      - **Problem 1:** Geographic ambiguity - User asks for "Scotland", tool returns "Scotland County, USA".
      - **Solution:** Re-run with qualified name: `places=["Scotland, UK"]`

      - **Problem 2:** Administrative level ambiguity - User asks for "New York", tool returns state-level data when city-level was intended.
      - **Solution:** Specify administrative level: `places=["New York City, USA"]` vs `places=["New York State, USA"]`

    ### Response Structure

    Returns a dictionary containing candidate indicators.

    ```json
    {
      "topics": [
        {
          "dcid": "dc/t/TopicDcid",
          "member_topics": ["dc/t/SubTopic1", "..."],
          "member_variables": ["dc/v/Variable1", "..."],
          "places_with_data": ["geoId/06", "..."]
        }
      ],
      "variables": [
        {
          "dcid": "dc/v/VariableDcid",
          "places_with_data": ["geoId/06", "country/CAN", "..."]
        }
      ],
      "dcid_name_mappings": {
        "dc/t/TopicDcid": "Readable Topic Name",
        "dc/v/VariableDcid": "Readable Variable Name",
        "geoId/06": "California",
        "country/CAN": "Canada"
      },
      "dcid_place_type_mappings": {
        "geoId/06": ["State"],
        "country/CAN": ["Country"]
      },
      "status": "SUCCESS"
    }

    ### How to Process the Response

      - `topics`: (Only if `include_topics=True`) Collections of variables and sub-topics. Use `dcid_name_mappings` to get readable names for presentation.

      - `variables`: Individual data indicators. Use `dcid_name_mappings` to get readable names.

      - `places_with_data`: (Only if `places` was in the request) A list of *DCIDs* for the requested places that have data for that specific indicator.

      - `dcid_name_mappings`: A dictionary mapping all DCIDs (topics, variables, and places) in the response to their human-readable names.

      - `dcid_place_type_mappings`: A dictionary mapping place DCIDs to their types (e.g., `["State"]`, `["Country"]`). Use this for child place type determination in `get_observations`.

    **Final Reminder:** Always treat results as *candidates*. You must filter and rank them based on the user's full context.
    """
    # Call the real search_indicators service
    return await search_indicators_service(
        client=dc_client,
        query=query,
        places=places,
        per_search_limit=per_search_limit,
        include_topics=include_topics,
        maybe_bilateral=maybe_bilateral,
    )
