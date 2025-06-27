"""
Clients module for interacting with Data Commons instances.
Provides classes for managing connections to both base and custom Data Commons instances.
"""

import asyncio
import requests
from datacommons_client.client import DataCommonsClient
import json
from cache import LruCache
import re
from constants import BASE_DC_ID
from topics import TopicStore, read_topic_cache


class DCClient:

  def __init__(self,
               dc_name: str = "Data Commons",
               base_url: str = None,
               api_key: str = None,
               sv_search_base_url: str = 'https://dev.datacommons.org',
               idx: str = 'base_uae_mem',
               topic_store: TopicStore = TopicStore(topics_by_dcid={}, all_variables=set())):
    """
    Initialize the DCClient with either an API key or a base URL.
    
    Args:
        api_key: API key for authentication (mutually exclusive with base_url)
        base_url: Base URL for custom Data Commons instance (mutually exclusive with api_key)
        sv_search_base_url: Base URL for SV search endpoint
        idx: Index to use for SV search
    """
    if api_key and base_url:
      raise ValueError("Cannot specify both api_key and base_url")
    elif not api_key and not base_url:
      raise ValueError("Must specify either api_key or base_url")

    self.dc_name = dc_name
    self.sv_search_base_url = sv_search_base_url
    self.idx = idx
    self.variable_cache = LruCache(128)
    self.topic_store = topic_store

    if api_key:
      self.dc = DataCommonsClient(api_key=api_key)
    else:
      self.dc = DataCommonsClient(url=base_url)

  def fetch_obs(self, sv_dcids: list[str], place_dcids: list[str]) -> dict:
    return self.dc.observation.fetch(
        variable_dcids=sv_dcids,
        entity_dcids=place_dcids,
        date="all",
    ).to_dict()

  def fetch_obs_for_child_places(self,
                                 sv_dcids: list[str],
                                 parent_place_dcid: str,
                                 child_place_type: str,
                                 date: str = "LATEST") -> dict:
    return self.dc.observation.fetch_observations_by_entity_type(
        variable_dcids=sv_dcids,
        parent_entity=parent_place_dcid,
        entity_type=child_place_type,
        date=date,
    ).to_dict()

  def fetch_entity_names(self, dcids: list[str]) -> dict:
    response = self.dc.node.fetch_entity_names(entity_dcids=dcids)
    return {dcid: name.value for dcid, name in response.items()}

  async def fetch_topic_variables(self, place_dcid: str, topic_query: str = "statistics") -> dict:
    """
    Fetch the variables for a place and topic.

    The variables are filtered to be the intersection
    of the topic variables and the variables available for the place.
    """
    all_variables = self.variable_cache.get(place_dcid)

    if all_variables is None:
      # If not in cache, fetch from API
      response = self.dc.observation.fetch_available_statistical_variables(
          entity_dcids=[place_dcid])
      unfiltered_variables = response.get(place_dcid, [])
      # Filter out internal "dc/alpha-numeric-string" variables that look like IDs.
      # These variables don't seem to have a name so not sure if they are useful.
      # TODO: This is a hack to filter out internal variables that look like IDs.
      # We should find a better way to do this or fix the schema so they have names.
      # TODO: Since we're only supporting topic variables now, should we only keep those that are in the topic store?
      all_variables = [
          var for var in unfiltered_variables
          if self.topic_store.has_variable(var) or 
             not re.fullmatch(r"dc/[a-z0-9]{10,}", var)
      ]
      # Store the full filtered list in the cache
      self.variable_cache.put(place_dcid, all_variables)

    topic_svs = await self._get_topic_svs(topic_query)
    all_vars_set = set(all_variables)
    # Get an intersection of the topic SVs and the place SVs while maintaining order.
    topic_svs = [
        sv for sv in topic_svs if sv in all_vars_set
    ]
    return {"topic_variable_ids": topic_svs}

  async def search_places(self, names: list[str]) -> dict:
    results_map = {}
    response = self.dc.resolve.fetch_dcids_by_name(names=names)
    data = response.to_dict()
    entities = data.get("entities", [])
    for entity in entities:
      node, candidates = entity.get('node', ''), entity.get("candidates", [])
      if node and candidates:
        results_map[node] = candidates[0].get('dcid', '')
    return results_map

  async def _get_topic_svs(self, topic_query: str) -> list[str]:
    """
    Get the SVs for a given topic.

    This is done by searching for the topic and finding the first result that
    is a topic. Then all the SVs that came before that topic in the search
    results are combined with all the SVs in that topic.
    """

    # TODO: This is clearly a hack to get the variables for the statistics topic.
    # This is because when searching for "statistics", the first result is an agriculture topic and the statistics topic is nowhere to be found.
    # We are special casing this because "statistics" is the default category for the tool and we want to return the variables for the statistics topic.
    # We should find a better way to do this.
    if topic_query.lower().strip() == "statistics":
      return self.topic_store.get_topic_variables("dc/topic/Root")
    
    # Search for SVs and topics, the results are ordered by relevance.
    search_results = await self.search_svs([topic_query], skip_topics=False)
    sv_topic_results = search_results.get(topic_query, [])

    if not sv_topic_results:
      return []

    svs_before_topic = []
    for result in sv_topic_results:
      sv_dcid = result.get("SV", "")
      if not sv_dcid:
        continue

      # A topic is identified by "topic/" in its dcid.
      if "topic/" in sv_dcid:
        topic_svs = self.topic_store.get_topic_variables(sv_dcid)

        # Combine SVs found before the topic with the SVs from the topic.
        # Using dict.fromkeys preserves order and removes duplicates.
        combined_svs = dict.fromkeys(svs_before_topic + topic_svs)
        return list(combined_svs.keys())
      else:
        # This is a regular SV that appeared before the first topic.
        svs_before_topic.append(sv_dcid)

    # If no topic was found, return all the SVs found in the search.
    return svs_before_topic
  
  async def search_svs(self, queries: list[str], skip_topics: bool = True) -> dict:
    results_map = {}
    skip_topics_param = "&skip_topics=true" if skip_topics else ""
    endpoint_url = f"{self.sv_search_base_url}/api/nl/search-vector"
    api_endpoint = f"{endpoint_url}?idx={self.idx}{skip_topics_param}"
    headers = {"Content-Type": "application/json"}

    for query in queries:
      payload = {"queries": [query]}
      try:
        response = requests.post(api_endpoint,
                                 data=json.dumps(payload),
                                 headers=headers)
        response.raise_for_status()
        data = response.json()
        results = data.get("queryResults", {})

        if query in results and "SV" in results[
            query] and "CosineScore" in results[query]:
          sv_list = results[query]["SV"]
          score_list = results[query]["CosineScore"]
          sorted_results = sorted(zip(sv_list, score_list),
                                  key=lambda x: (-x[1], x[0]))
          sv_list, score_list = zip(*sorted_results)

          # Assuming len(sv_list) == len(score_list) as per user prompt
          # Iterate up to the top 5, or fewer if less than 5 results are available.
          num_results_available = len(sv_list)
          num_results_to_take = min(num_results_available, 5)

          top_results = []
          for i in range(num_results_to_take):
            top_results.append({"SV": sv_list[i], "CosineScore": score_list[i]})
          results_map[query] = top_results
        else:
          # This case handles if the query is in the response, but SV/CosineScore is missing/empty
          results_map[query] = []

      except Exception as e:
        print(f"An unexpected error occurred for query '{query}': {e}")
        results_map[query] = []
    return results_map

  async def child_place_type_exists(self, parent_place_dcid: str,
                                    child_place_type: str) -> bool:
    response = self.dc.node.fetch_place_children(place_dcids=parent_place_dcid,
                                                 children_type=child_place_type,
                                                 as_dict=True)
    return len(response.get(parent_place_dcid, [])) > 0


class MultiDCClient:

  def __init__(self, base_dc: DCClient, custom_dcs: list[DCClient]):
    self.base_dc = base_dc
    self.custom_dcs = custom_dcs
    # Map DC IDs to DCClient instances
    self.dc_map = {
        BASE_DC_ID: base_dc,
        **{
            dc.sv_search_base_url: dc for dc in custom_dcs
        }
    }
    self.min_custom_score = 0.7
    # For the DC federation case (i.e. more than one custom DC), raise the threshold to 0.8
    if self.custom_dcs and len(self.custom_dcs) >= 2:
      self.min_custom_score = 0.8

  async def search_svs(self, queries: list[str]) -> dict:
    """
        Search for SVs across all DC instances.
        
        Returns:
            A dictionary where:
            - keys are the input queries
            - values are dictionaries containing:
                - 'SV': The selected SV
                - 'CosineScore': The score of the SV
                - 'dc_id': The ID of the DC that provided the SV
        """
    results = {}

    # Search across all DCs in parallel
    all_results = await asyncio.gather(
        *[dc.search_svs(queries) for dc in [self.base_dc] + self.custom_dcs])

    for query in queries:
      # Find the best SV from custom DCs first
      best_custom_result = None
      best_custom_score = self.min_custom_score

      for idx, dc_results in enumerate(all_results[1:],
                                       1):  # Skip base DC results
        if query in dc_results:
          for result in dc_results[query]:
            if result['CosineScore'] > best_custom_score:
              best_custom_score = result['CosineScore']
              best_custom_result = {
                  'SV': result['SV'],
                  'CosineScore': result['CosineScore'],
                  'dc_id': self.custom_dcs[idx - 1].sv_search_base_url
              }

      # If no good custom result, use base DC result
      if not best_custom_result:
        base_results = all_results[0]
        if query in base_results and base_results[query]:
          best_result = {
              'SV': base_results[query][0]['SV'],
              'CosineScore': base_results[query][0]['CosineScore'],
              'dc_id': BASE_DC_ID
          }
        else:
          best_result = None
      else:
        best_result = best_custom_result

      results[query] = best_result

    return results

  async def fetch_obs(self, dc_id: str, sv_dcid: str, place_dcid: str) -> dict:
    # Get the DC client from the ID
    dc = self.dc_map.get(dc_id)
    if not dc:
      raise ValueError(f"Unknown DC ID: {dc_id}")

    return dc.fetch_obs([sv_dcid], [place_dcid])

  async def fetch_obs_for_child_places(self,
                                       dc_id: str,
                                       sv_dcids: list[str],
                                       parent_place_dcid: str,
                                       child_place_type: str,
                                       date: str = "LATEST") -> dict:
    # Get the DC client from the ID
    dc = self.dc_map.get(dc_id)
    if not dc:
      raise ValueError(f"Unknown DC ID: {dc_id}")

    return dc.fetch_obs_for_child_places(sv_dcids, parent_place_dcid,
                                         child_place_type, date)


def create_clients(config: dict) -> MultiDCClient:
  """
    Factory function to create MultiDCClient based on configuration.
    
    Args:
        config: Dictionary containing client configurations
            Expected format:
            {
                "base": {  # Base DC configuration
                    "api_key": "your_api_key",
                    "sv_search_base_url": "base_url",
                    "idx": "index",
                    "topic_cache_path": "path/to/topic_cache.json"
                },
                "custom_dcs": [  # List of custom DC configurations
                    {
                        "base_url": "custom_url",
                        "sv_search_base_url": "custom_url",
                        "idx": "index",
                        "name": "Custom Name"
                    }
                ]
            }
    """
  base_config = config.get("base", {})
  custom_configs = config.get("custom_dcs", [])

  # Create base DC client
  base_dc = DCClient(dc_name="Data Commons",
                     api_key=base_config.get("api_key"),
                     sv_search_base_url=base_config.get("sv_search_base_url"),
                     idx=base_config.get("idx"),
                     topic_store=read_topic_cache())

  # Create custom DC clients
  custom_dcs = []
  for custom_config in custom_configs:
    custom_dc = DCClient(
        dc_name=custom_config.get("name", "Custom DC"),
        base_url=custom_config.get("base_url"),
        sv_search_base_url=custom_config.get("sv_search_base_url"),
        idx=custom_config.get("idx"))
    custom_dcs.append(custom_dc)

  return MultiDCClient(base_dc, custom_dcs)
