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
    children: List[str] = field(default_factory=list)


@dataclass
class TopicVariables:
    """Represents a topic and its flattened list of unique statistical variables."""

    topic_dcid: str
    topic_name: str
    variables: List[str] = field(default_factory=list)


@dataclass
class TopicStore:
    """A wrapper for the topic cache data."""

    topics_by_dcid: Dict[str, TopicVariables]
    all_variables: Set[str]

    def has_variable(self, sv_dcid: str) -> bool:
        return sv_dcid in self.all_variables

    def get_topic_variables(self, topic_dcid: str) -> list[str]:
        topic_data = self.topics_by_dcid.get(topic_dcid)
        return topic_data.variables if topic_data else []


def _flatten_variables_recursive(
    node: Node,
    nodes_by_dcid: Dict[str, Node],
    all_vars: Dict[str, None],
    visited: Set[str],
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
        all_nodes: List[Node] = []
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
    nodes_by_dcid: Dict[str, Node] = {
        node.dcid: node for node in all_nodes if node.dcid
    }

    final_topic_variables: Dict[str, TopicVariables] = {}
    all_topics = [
        node for node in all_nodes if node.type_of == _TYPE_TOPIC and node.dcid
    ]

    for topic in all_topics:
        ordered_unique_vars: Dict[str, None] = {}
        visited_nodes: Set[str] = set()

        _flatten_variables_recursive(
            topic, nodes_by_dcid, ordered_unique_vars, visited_nodes
        )

        final_topic_variables[topic.dcid] = TopicVariables(
            topic_dcid=topic.dcid,
            topic_name=topic.name,
            variables=list(ordered_unique_vars.keys()),
        )

    all_variables_set: Set[str] = set()
    for topic_vars in final_topic_variables.values():
        all_variables_set.update(topic_vars.variables)

    return TopicStore(
        topics_by_dcid=final_topic_variables, all_variables=all_variables_set
    )
