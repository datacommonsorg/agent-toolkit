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

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set

from datacommons_client.client import DataCommonsClient

# Constants
_SOURCE_DIR = Path(__file__).resolve().parent
_TYPE_TOPIC = "Topic"
_DCID_PREFIX_TOPIC = "topic/"
_DCID_PREFIX_SVPG = "svpg/"
_DEFAULT_TOPIC_CACHE_PATH = _SOURCE_DIR / "topic_cache.json"


@dataclass
class Node:
    """Represents a generic node in the topic hierarchy."""

    dcid: str
    name: str
    type_of: str
    children: list[str] = field(default_factory=list)


@dataclass
class TopicVariables:
    """Represents a topic and its members (both sub-topics and variables)."""

    topic_dcid: str
    topic_name: str
    variables: list[str] = field(default_factory=list)
    member_topics: list[str] = field(default_factory=list)


@dataclass
class NodeData:
    """Represents the parsed data from a node API response."""

    name: str
    relevant_variables: list[str]
    relevant_names: dict[str, str] = field(default_factory=dict)

    def get_variables(self) -> list[str]:
        """Extract variable DCIDs from relevant_variables."""
        variables = []
        for var in self.relevant_variables:
            if not _is_topic_dcid(var):
                variables.append(var)
        return variables

    def get_member_topics(self) -> list[str]:
        """Extract topic DCIDs from relevant_variables."""
        topics = []
        for var in self.relevant_variables:
            if _is_topic_dcid(var):
                topics.append(var)
        return topics

    def get_variable_names(self) -> dict[str, str]:
        """Get the mapping of variable DCIDs to their names."""
        return {
            dcid: name
            for dcid, name in self.relevant_names.items()
            if not _is_topic_dcid(dcid)
        }

    def get_topic_names(self) -> dict[str, str]:
        """Get the mapping of topic DCIDs to their names."""
        return {
            dcid: name
            for dcid, name in self.relevant_names.items()
            if _is_topic_dcid(dcid)
        }


@dataclass
class TopicStore:
    """A wrapper for the topic cache data."""

    topics_by_dcid: dict[str, TopicVariables]
    all_variables: set[str]
    dcid_to_name: dict[str, str] = field(default_factory=dict)

    def has_variable(self, sv_dcid: str) -> bool:
        return sv_dcid in self.all_variables

    def get_topic_variables(self, topic_dcid: str) -> list[str]:
        topic_data = self.topics_by_dcid.get(topic_dcid)
        return topic_data.variables if topic_data else []

    def get_topic_members(self, topic_dcid: str) -> list[str]:
        """Get both member topics and variables for a topic."""
        topic_data = self.topics_by_dcid.get(topic_dcid)
        if not topic_data:
            return []
        return topic_data.member_topics + topic_data.variables

    def get_member_topics(self, topic_dcid: str) -> list[str]:
        """Get only member topics (not variables) for a topic."""
        topic_data = self.topics_by_dcid.get(topic_dcid)
        return topic_data.member_topics if topic_data else []

    def get_name(self, dcid: str) -> str:
        """Get the human-readable name for a DCID."""
        return self.dcid_to_name.get(dcid, dcid)


def _flatten_variables_recursive(
    node: Node,
    nodes_by_dcid: dict[str, Node],
    all_vars: dict[str, None],
    visited: set[str],
) -> None:
    """
    Recursively traverses the topic/svpg structure to collect unique variable DCIDs.
    It uses a dictionary as an ordered set to maintain insertion order.
    """
    if node.dcid in visited:
        return
    visited.add(node.dcid)

    for child_dcid in node.children:
        child_node = nodes_by_dcid.get(child_dcid)

        if child_node:
            _flatten_variables_recursive(child_node, nodes_by_dcid, all_vars, visited)
        else:
            # The child is NOT a defined node. Assume it's a variable,
            # but ignore broken topic/svpg links.
            if _DCID_PREFIX_TOPIC in child_dcid or _DCID_PREFIX_SVPG in child_dcid:
                continue
            if child_dcid not in all_vars:
                all_vars[child_dcid] = None


def read_topic_cache(file_path: Path = _DEFAULT_TOPIC_CACHE_PATH) -> TopicStore:
    """
    Reads the topic_cache.json file, parses the hierarchical structure,
    and returns a TopicStore containing the topic map and a set of all variables.
    """
    with file_path.open("r") as f:
        # Manually process the raw JSON to handle the list-based fields
        raw_data = json.load(f)
        all_nodes: list[Node] = []
        for node_data in raw_data.get("nodes", []):
            members = node_data.get("memberList", [])
            relevant_vars = node_data.get("relevantVariableList", [])
            all_nodes.append(
                Node(
                    dcid=node_data.get("dcid", [""])[0],
                    name=node_data.get("name", [""])[0],
                    type_of=node_data.get("typeOf", [""])[0],
                    children=members + relevant_vars,
                )
            )

    # Create a lookup for all nodes by their DCID
    nodes_by_dcid: dict[str, Node] = {
        node.dcid: node for node in all_nodes if node.dcid
    }

    final_topic_variables: dict[str, TopicVariables] = {}
    all_topics = [
        node for node in all_nodes if node.type_of == _TYPE_TOPIC and node.dcid
    ]

    for topic in all_topics:
        ordered_unique_vars: dict[str, None] = {}
        visited_nodes: set[str] = set()

        _flatten_variables_recursive(
            topic, nodes_by_dcid, ordered_unique_vars, visited_nodes
        )

        final_topic_variables[topic.dcid] = TopicVariables(
            topic_dcid=topic.dcid,
            topic_name=topic.name,
            variables=list(ordered_unique_vars.keys()),
        )

    all_variables_set: set[str] = set()
    for topic_vars in final_topic_variables.values():
        all_variables_set.update(topic_vars.variables)

    return TopicStore(
        topics_by_dcid=final_topic_variables, all_variables=all_variables_set
    )


def _fetch_node_data(
    topic_dcids: List[str], dc_client: DataCommonsClient
) -> Dict[str, NodeData]:
    """
    Fetch node data for the given topic DCIDs using DataCommonsClient.

    Args:
        topic_dcids: List of topic DCIDs to fetch
        dc_client: DataCommonsClient instance

    Returns:
        Dictionary mapping DCID to NodeData objects
    """
    if not topic_dcids:
        return {}

    try:
        response = dc_client.node.fetch(
            node_dcids=topic_dcids, expression="->[name, relevantVariable]"
        )

        # Create a mapping of DCID to NodeData objects
        nodes_by_dcid: dict[str, NodeData] = {}

        response_dict = response.to_dict()
        for dcid, node_data in response_dict.get("data", {}).items():
            # Extract name from the arcs structure
            name_nodes = node_data.get("arcs", {}).get("name", {}).get("nodes", [])
            name = name_nodes[0].get("value", "") if name_nodes else ""

            # Extract relevantVariable from the arcs structure
            relevant_var_nodes = (
                node_data.get("arcs", {}).get("relevantVariable", {}).get("nodes", [])
            )
            relevant_variables = []
            relevant_names = {}

            for var_node in relevant_var_nodes:
                var_dcid = var_node.get("dcid", "")
                var_name = var_node.get("name", "")
                if var_dcid:
                    relevant_variables.append(var_dcid)
                    if var_name:
                        relevant_names[var_dcid] = var_name

            nodes_by_dcid[dcid] = NodeData(
                name=name,
                relevant_variables=relevant_variables,
                relevant_names=relevant_names,
            )

        return nodes_by_dcid
    except Exception as e:
        print(f"Error fetching node data: {e}")
        return {}


def _is_topic_dcid(dcid: str) -> bool:
    """Check if a DCID represents a topic."""
    return "/topic/" in dcid


def _collect_descendant_variables(
    topic_dcid: str,
    topics_by_dcid: Dict[str, TopicVariables],
    visited: Set[str],
) -> Set[str]:
    """
    Recursively collect all descendant variables for a given topic.
    
    Args:
        topic_dcid: The topic DCID to collect descendants for
        topics_by_dcid: Dictionary of all topics
        visited: Set of already visited topics to prevent cycles
        
    Returns:
        Set of all descendant variable DCIDs
    """
    if topic_dcid in visited:
        return set()
    
    visited.add(topic_dcid)
    topic_data = topics_by_dcid.get(topic_dcid)
    if not topic_data:
        return set()
    
    # Start with direct variables
    descendant_vars = set(topic_data.variables)
    
    # Add variables from all member topics
    for member_topic in topic_data.member_topics:
        member_vars = _collect_descendant_variables(
            member_topic, topics_by_dcid, visited
        )
        descendant_vars.update(member_vars)
    
    return descendant_vars


def _save_topic_store_to_cache(topic_store: TopicStore, cache_file_path: Path) -> None:
    """
    Save a TopicStore to a cache file.

    Args:
        topic_store: The TopicStore to save
        cache_file_path: Path to the cache file
    """

    # Convert TopicStore to a serializable format
    cache_data = {
        "topics_by_dcid": {
            dcid: {
                "topic_dcid": topic_data.topic_dcid,
                "topic_name": topic_data.topic_name,
                "variables": topic_data.variables,
                "member_topics": topic_data.member_topics,
            }
            for dcid, topic_data in topic_store.topics_by_dcid.items()
        },
        "all_variables": list(topic_store.all_variables),
        "dcid_to_name": topic_store.dcid_to_name,
    }

    # Ensure the directory exists
    cache_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Save to file
    with open(cache_file_path, "w") as f:
        json.dump(cache_data, f, indent=2)


def _load_topic_store_from_cache(cache_file_path: Path) -> TopicStore:
    """
    Load a TopicStore from a cache file.

    Args:
        cache_file_path: Path to the cache file

    Returns:
        TopicStore loaded from cache
    """

    with open(cache_file_path, "r") as f:
        cache_data = json.load(f)

    # Reconstruct TopicStore from cache data
    topics_by_dcid = {
        dcid: TopicVariables(
            topic_dcid=topic_data["topic_dcid"],
            topic_name=topic_data["topic_name"],
            variables=topic_data["variables"],
            member_topics=topic_data.get("member_topics", []),
        )
        for dcid, topic_data in cache_data["topics_by_dcid"].items()
    }

    all_variables = set(cache_data["all_variables"])
    dcid_to_name = cache_data["dcid_to_name"]

    return TopicStore(
        topics_by_dcid=topics_by_dcid,
        all_variables=all_variables,
        dcid_to_name=dcid_to_name,
    )


def create_topic_store(
    root_topic_dcids: List[str],
    dc_client: DataCommonsClient,
    cache_file_path: Path | None = None,
) -> TopicStore:
    """
    Recursively fetch topic data using DataCommonsClient and create a TopicStore.
    If a cache file is provided and exists, load from cache. Otherwise fetch from API and cache the result.

    Args:
        root_topic_dcids: List of root topic DCIDs to fetch
        dc_client: DataCommonsClient instance
        cache_file_path: Optional path to cache file for faster loading during development

    Returns:
        TopicStore instance with topics and their variables
    """
    # Try to load from cache first
    if cache_file_path and cache_file_path.exists():
        try:
            print(f"Loading topic store from cache: {cache_file_path}")
            return _load_topic_store_from_cache(cache_file_path)
        except Exception as e:
            print(f"Failed to load from cache: {e}")
            print("Falling back to API fetch...")

    # Fetch from API
    topics_by_dcid: Dict[str, TopicVariables] = {}
    all_variables: Set[str] = set()
    dcid_to_name: Dict[str, str] = {}
    visited_topics: Set[str] = set()
    topics_to_fetch: Set[str] = set(root_topic_dcids)

    while topics_to_fetch:
        # Fetch data for current batch of topics
        current_topics = list(topics_to_fetch)
        topics_to_fetch.clear()

        nodes_data = _fetch_node_data(current_topics, dc_client)

        for topic_dcid in current_topics:
            if topic_dcid in visited_topics:
                continue

            visited_topics.add(topic_dcid)
            node_data = nodes_data.get(topic_dcid)

            if not node_data:
                continue

            # Extract topic name
            topic_name = node_data.name

            # Store topic name in dcid_to_name mapping
            if topic_name:
                dcid_to_name[topic_dcid] = topic_name

            # Extract variables and sub-topics
            variables = node_data.get_variables()
            sub_topics = node_data.get_member_topics()

            # Store variable names in dcid_to_name mapping
            variable_names = node_data.get_variable_names()
            dcid_to_name.update(variable_names)

            # Add variables to the set
            all_variables.update(variables)

            # Add sub-topics to the fetch queue
            for sub_topic in sub_topics:
                if sub_topic not in visited_topics:
                    topics_to_fetch.add(sub_topic)

            # Create TopicVariables for this topic
            topics_by_dcid[topic_dcid] = TopicVariables(
                topic_dcid=topic_dcid,
                topic_name=topic_name,
                variables=variables,
                member_topics=sub_topics,
            )

    # After all topics have been fetched, populate each topic with all its descendant variables
    for topic_dcid in topics_by_dcid:
        descendant_vars = _collect_descendant_variables(
            topic_dcid, topics_by_dcid, set()
        )
        # Update the topic's variables to include all descendants
        topics_by_dcid[topic_dcid].variables = list(descendant_vars)
        # Update the all_variables set
        all_variables.update(descendant_vars)

    topic_store = TopicStore(
        topics_by_dcid=topics_by_dcid,
        all_variables=all_variables,
        dcid_to_name=dcid_to_name,
    )

    # Cache the result if a cache file path is provided
    if cache_file_path:
        try:
            print(f"Caching topic store to: {cache_file_path}")
            _save_topic_store_to_cache(topic_store, cache_file_path)
        except Exception as e:
            print(f"Failed to cache topic store: {e}")

    return topic_store
