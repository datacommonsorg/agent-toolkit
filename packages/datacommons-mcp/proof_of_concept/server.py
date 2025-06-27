"""
Server module for the DC MCP server.
"""

import asyncio
import types
from typing import Optional, Union, get_args, get_origin
from fastmcp import FastMCP
from clients import create_clients
from response_transformers import transform_obs_response
import config
from datacommons_chart_types import DataCommonsChartConfig, CHART_CONFIG_MAP, SinglePlaceLocation, MultiPlaceLocation, SingleVariableChart, HierarchyLocation
from pydantic import ValidationError
from constants import BASE_DC_ID

# Create clients based on config
multi_dc_client = create_clients(config.BASE_DC_CONFIG)

mcp = FastMCP("DC MCP Server")


@mcp.tool()
async def get_observations(variable_desc: Optional[str] = None,
                           variable_dcid: Optional[str] = None,
                           place_name: Optional[str] = None,
                           place_dcid: Optional[str] = None,
                           facet_id_override: Optional[str] = None) -> dict:
  """Get observations for a given concept or indicator (called a statistical variable in Data Commons parlance) about a place from Data Commons.
    This tool can retrieve various types of data, including time series, single values,
    or categorical information, depending on the concept requested and the available data.

    Note: This tool retrieves observations for all dates.
    Unlike get_observations_for_child_places, this tool does NOT support filtering the results by a specific date.

    You must provide either a variable_desc or a variable_dcid, but not both.
    You must provide either a place_name or a place_dcid, but not both.

    Guidance on Variable Selection:

    When the user is asking for data about a place_name or place_dcid for which 
    you have previously successfully called get_available_variables_for_place, 
    you will have access to a list of available variable DCIDs and their id_name_mappings.

    Prioritization: Before attempting to use the variable_desc parameter, 
    if you have previously called get_available_variables_for_place for this place,
    FIRST examine the user's request and compare it to the id_name_mappings 
    you already possess for this place.

    If you find a variable name in your id_name_mappings that appears to be a close 
    or exact match to the concept or indicator the user is asking for, 
    use the corresponding variable_dcid in your call to get_observations. 
    This is the preferred method when relevant DCIDs are known.
    Example: If the user asks for "mean rainfall in Mumbai" and your id_name_mappings 
    for Mumbai includes "Mean_Rainfall": "Mean Rainfall", 
    use variable_dcid="Mean_Rainfall" and place_dcid="wikidataId/Q1156" 
    (assuming you have the place DCID).

    Fallback: If you cannot find a sufficiently relevant variable name 
    in your existing id_name_mappings for the requested place, 
    should you use the variable_desc parameter to provide a natural language description 
    of the variable you are looking for.
    
    Args:
      variable_desc (str, optional): The concept or indicator to fetch data for.
        Provide a natural language description of what data you are looking for.
        Examples: "population", "gdp", "carbon emissions", "unemployment rate".
      variable_dcid (str, optional): The DCID of the statistical variable.
      place_name (str, optional): The name of the place to fetch the data for. e.g. "United States", "India", "NYC".
      place_dcid (str, optional): The DCID of the place.
      facet_id_override (str, optional): An optional facet ID to force the selection of a specific data source.
        If not specified, the tool will select the best data source based on the observation count.
    Returns:
      dict: A dictionary containing the status of the request and the data if available.

      The dictionary has the following format:
      {
        "status": "SUCCESS" | "NO_DATA_FOUND" | "ERROR",
        "data": <data_by_variable>,
        "message": "..."
      }

      The data has the following format:
      {
            "dc_provider": "...",
            "lookups": {
                "id_name_mappings": { ... }
            },
            "data_by_variable": {
                "variable_id_1": {
                    "source": {
                        "facet_id": "best_facet_id",
                        "provenanceUrl": "...",
                        "unit": "...",
                        "observation_count": 120
                    },
                    "observations": [
                        ["entity_id_1", "date_1", "value_1"],
                        ["entity_id_2", "date_2", "value_2"]
                    ],
                    "other_available_sources": [
                        {
                            "facet_id": "other_facet_456",
                            "provenanceUrl": "...",
                            "unit": "...",
                            "observation_count": 50
                        }
                    ]
                }
            }
        }

      The facet_id is a unique identifier for the data source.
      Data is returned from a single source (facet).
      Other available sources are returned in the other_available_sources list.
      If the user asks for a specific data source, you can use the facet_id_override to force the selection of that source.

      In your response, use the id_name_mappings to convert the variable_id, entity_id, and facet_id to human-readable names.

      Also, cite the source of the data in your response and suffix it with "(Powered by {dc_provider})".
    """
  # 1. Input validation
  if not (variable_desc or variable_dcid) or (variable_desc and variable_dcid):
    return {
        "status":
            "ERROR",
        "message":
            "Specify either 'variable_desc' or 'variable_dcid', but not both."
    }

  if not (place_name or place_dcid) or (place_name and place_dcid):
    return {
        "status": "ERROR",
        "message": "Specify either 'place_name' or 'place_dcid', but not both."
    }

  # 2. Concurrently resolve identifiers if needed
  tasks = {}
  if variable_desc:
    tasks['sv_search'] = multi_dc_client.search_svs([variable_desc])
  if place_name:
    tasks['place_search'] = multi_dc_client.base_dc.search_places([place_name])

  svs = None
  places = None
  if tasks:
    # Use asyncio.gather on the values (coroutines) of the tasks dict
    task_coroutines = list(tasks.values())
    task_results = await asyncio.gather(*task_coroutines)
    # Map results back to their keys
    results = dict(zip(tasks.keys(), task_results))
    svs = results.get('sv_search')
    places = results.get('place_search')

  # 3. Process results and set DCIDs
  sv_dcid_to_use = variable_dcid
  dc_id_to_use = BASE_DC_ID if variable_dcid else None
  place_dcid_to_use = place_dcid

  if svs:
    sv_data = svs.get(variable_desc, {})
    print(f"sv_data: {variable_desc} -> {sv_data}")
    dc_id_to_use = sv_data.get('dc_id')
    sv_dcid_to_use = sv_data.get('SV', '')

  if places:
    place_dcid_to_use = places.get(place_name, '')
    print(f"place: {place_name} -> {place_dcid_to_use}")

  # 4. Final validation and fetch
  if not sv_dcid_to_use or not place_dcid_to_use or not dc_id_to_use:
    return {"status": "NO_DATA_FOUND"}

  response = await multi_dc_client.fetch_obs(dc_id_to_use, sv_dcid_to_use,
                                             place_dcid_to_use)
  dc_client = multi_dc_client.dc_map.get(dc_id_to_use)
  response['dc_provider'] = dc_client.dc_name

  return {
      "status":
          "SUCCESS",
      "data":
          transform_obs_response(response,
                                 dc_client.fetch_entity_names,
                                 facet_id_override=facet_id_override)
  }


@mcp.tool()
async def validate_child_place_types(
    parent_place_name: str, child_place_types: list[str]) -> dict[str, bool]:
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
  place_dcid = places.get(parent_place_name, '')
  if not place_dcid:
    return {child_place_type: False for child_place_type in child_place_types}

  tasks = [
      multi_dc_client.base_dc.child_place_type_exists(
          place_dcid,
          child_place_type,
      ) for child_place_type in child_place_types
  ]

  results = await asyncio.gather(*tasks)

  return dict(zip(child_place_types, results))


@mcp.tool()
async def get_observations_for_child_places(
    variable_desc: str,
    parent_place_name: str,
    child_place_type: str,
    date: str = "LATEST",
    facet_id_override: Optional[str] = None) -> dict:
  """Get observations for a given concept or indicator (called a statistical variable in Data Commons parlance) 
    for all children of a given parent place of a given type from Data Commons.

    Use this tool when you want data for all smaller regions of a certain type in a larger region.
    For example, you can use this tool to get GDP for all states in the US, or population for all countries in Europe or in the World.

    This tool can retrieve various types of data, including time series, single values,
    or categorical information, depending on the concept requested and the available data.

    Args:
      variable_desc (str): The concept or indicator to fetch data for.
        Provide a natural language description of what data you are looking for about the place.
        Examples include: "population", "gdp", "carbon emissions", "unemployment rate",
        "years of free education", "average temperature", "dominant political party", etc.
        The tool has advanced internal logic to understand diverse requests and
        find the best matching data available in Data Commons, regardless of whether it's
        traditionally considered a 'statistical variable' or a 'time series'.
      parent_place_name (str): The larger geographic region or administrative division containing the places to fetch data for. 
        This can be a city, county, state, country, a continent (like "Europe" or "Asia"), or the entire world.
        Examples: "United States", "India", "NYC", "Europe", "World", etc.
      child_place_type (str): The type of the child places within the parent place to fetch data for. The valid types depend on the parent.
        Use the validate_child_place_types tool to check valid child place types for a given parent place. 
        Use the returned dictionary to determine the correct child place type when calling this tool.
      date (str): The date to fetch the data for. If not specified, the latest available data will be returned.
        The date should be in the format YYYY-MM-DD. e.g. "2022", "2022-01", "2022-01-01".
      facet_id_override (str): An optional facet ID to force the selection of a specific data source.
        If not specified, the tool will select the best data source based on the observation count.
      Example usage: To get GDP for countries in Europe, use parent_place_name="Europe" and child_place_type="Country".
    Returns:
      dict: A dictionary containing the status of the request and the data if available.
      
      The dictionary has the following format:
      {
        "status": "SUCCESS" | "NO_DATA_FOUND",
        "data": <data_by_variable>
      }

      The data has the following format:
      {
            "dc_provider": "...",
            "lookups": {
                "id_name_mappings": { ... }
            },
            "data_by_variable": {
                "variable_id_1": {
                    "source": {
                        "facet_id": "best_facet_id",
                        "provenanceUrl": "...",
                        "unit": "...",
                        "observation_count": 120
                    },
                    "observations": [
                        ["entity_id_1", "date_1", "value_1"],
                        ["entity_id_2", "date_2", "value_2"]
                    ],
                    "other_available_sources": [
                        {
                            "facet_id": "other_facet_456",
                            "provenanceUrl": "...",
                            "unit": "...",
                            "observation_count": 50
                        }
                    ]
                }
            }
        }

      The facet_id is a unique identifier for the data source.
      Data is returned from a single source (facet).
      Other available sources are returned in the other_available_sources list.
      If the user asks for a specific data source, you can use the facet_id_override to force the selection of that source.

      In your response, use the id_name_mappings to convert the variable_id, entity_id, and facet_id to human-readable names.

      Also, cite the source of the data in your response and suffix it with "(Powered by {dc_provider})".
    """
  svs, places = await asyncio.gather(
      multi_dc_client.search_svs([variable_desc]),
      multi_dc_client.base_dc.search_places([parent_place_name]),
  )

  sv_data = svs.get(variable_desc, {})
  print(f"sv_data: {variable_desc} -> {sv_data}")
  dc_id = sv_data.get('dc_id')
  sv_dcid = sv_data.get('SV', '')

  place_dcid = places.get(parent_place_name, '')
  print(f"place: {parent_place_name} -> {place_dcid}")

  if not sv_dcid or not place_dcid:
    return {"status": "NO_DATA_FOUND"}

  # Use the DC ID from the search results
  response = await multi_dc_client.fetch_obs_for_child_places(
      dc_id, [sv_dcid], place_dcid, child_place_type, date)
  dc_client = multi_dc_client.dc_map.get(dc_id)
  response['dc_provider'] = dc_client.dc_name

  return {
      "status":
          "SUCCESS",
      "data":
          transform_obs_response(response,
                                 dc_client.fetch_entity_names,
                                 other_dcids_to_lookup=[place_dcid],
                                 facet_id_override=facet_id_override)
  }


@mcp.tool()
async def get_available_variables(place_name: str = "world",
                                  category: str = "statistics") -> dict:
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
        "message": f"Could not find a place named '{place_name}'."
    }

  dc = multi_dc_client.base_dc
  variable_data = await dc.fetch_topic_variables(place_dcid,
                                                 topic_query=category)

  dcids_to_lookup = [place_dcid]

  topic_variable_ids = variable_data.get("topic_variable_ids", [])
  dcids_to_lookup.extend(topic_variable_ids)

  id_name_mappings = dc.fetch_entity_names(dcids_to_lookup)

  return {
      "status": "SUCCESS",
      "data": {
          "place_dcid": place_dcid,
          "topic_variable_ids": topic_variable_ids,
          "id_name_mappings": id_name_mappings
      }
  }


@mcp.tool()
async def get_datacommons_chart_config(
    chart_type: str,
    chart_title: str,
    variable_dcids: list[str],
    place_dcids: Optional[list[str]] = None,
    parent_place_dcid: Optional[str] = None,
    child_place_type: Optional[str] = None) -> DataCommonsChartConfig:
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
  ChartConfigClass = CHART_CONFIG_MAP.get(chart_type)
  if not ChartConfigClass:
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
    location_model = ChartConfigClass.model_fields['location'].annotation
    location_obj = None

    # Check if the annotation is a Union (e.g., Union[A, B] or A | B)
    if get_origin(location_model) in (Union, types.UnionType):
      # Get the types inside the Union, e.g., (SinglePlaceLocation, MultiPlaceLocation)
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
    elif HierarchyLocation in possible_location_types and (parent_place_dcid and
                                                           child_place_type):
      location_obj = HierarchyLocation(parent_place_dcid=parent_place_dcid,
                                       child_place_type=child_place_type)
    else:
      # The Union doesn't contain a type we can build
      raise ValueError(
          f"Chart type '{chart_type}' requires a location type "
          f"('{location_model.__name__}') that this function cannot build from "
          "the provided args.")

    if issubclass(ChartConfigClass, SingleVariableChart):
      return ChartConfigClass(header=chart_title,
                              location=location_obj,
                              variable_dcid=variable_dcids[0])

    else:
      return ChartConfigClass(header=chart_title,
                              location=location_obj,
                              variable_dcids=variable_dcids)

  except ValidationError as e:
    # Catch Pydantic errors and make them more user-friendly
    raise ValueError(
        f"Validation failed for chart_type '{chart_type}': {e}") from e


if __name__ == "__main__":
  asyncio.run(mcp.run_sse_async(host="0.0.0.0", port=8080))
