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

from datacommons_mcp.topics import TopicStore, TopicVariables, read_topic_caches


class TestTopicStoreMerge:
    """Test cases for TopicStore.merge() functionality."""

    def test_merge_non_overlapping_stores(self):
        """Test merging stores with no overlapping data."""
        # Store 1: Health topics
        store1 = TopicStore(
            topics_by_dcid={
                "topic/health": TopicVariables(
                    topic_dcid="topic/health",
                    topic_name="Health",
                    variables=["sv/health_var1", "sv/health_var2"],
                    member_topics=["topic/mental_health"],
                )
            },
            all_variables={"sv/health_var1", "sv/health_var2"},
            dcid_to_name={
                "topic/health": "Health",
                "topic/mental_health": "Mental Health",
                "sv/health_var1": "Health Variable 1",
                "sv/health_var2": "Health Variable 2",
            },
        )

        # Store 2: Economic topics
        store2 = TopicStore(
            topics_by_dcid={
                "topic/economy": TopicVariables(
                    topic_dcid="topic/economy",
                    topic_name="Economy",
                    variables=["sv/econ_var1", "sv/econ_var2"],
                    member_topics=["topic/trade"],
                )
            },
            all_variables={"sv/econ_var1", "sv/econ_var2"},
            dcid_to_name={
                "topic/economy": "Economy",
                "topic/trade": "Trade",
                "sv/econ_var1": "Economic Variable 1",
                "sv/econ_var2": "Economic Variable 2",
            },
        )

        result = store1.merge(store2)

        # Verify merged topics
        expected_topics = {"topic/health", "topic/economy"}
        assert set(result.topics_by_dcid.keys()) == expected_topics

        # Verify merged variables
        expected_variables = {
            "sv/health_var1",
            "sv/health_var2",
            "sv/econ_var1",
            "sv/econ_var2",
        }
        assert result.all_variables == expected_variables

        # Verify merged names
        expected_names = {
            "topic/health": "Health",
            "topic/mental_health": "Mental Health",
            "topic/economy": "Economy",
            "topic/trade": "Trade",
            "sv/health_var1": "Health Variable 1",
            "sv/health_var2": "Health Variable 2",
            "sv/econ_var1": "Economic Variable 1",
            "sv/econ_var2": "Economic Variable 2",
        }
        assert result.dcid_to_name == expected_names

    def test_merge_overlapping_stores(self):
        """Test merging stores with overlapping data (first store should prevail)."""
        # Store 1: Initial data (this should prevail)
        store1 = TopicStore(
            topics_by_dcid={
                "topic/health": TopicVariables(
                    topic_dcid="topic/health",
                    topic_name="Health",
                    variables=["sv/health_var1"],
                    member_topics=[],
                )
            },
            all_variables={"sv/health_var1"},
            dcid_to_name={
                "topic/health": "Health",
                "sv/health_var1": "Health Variable 1",
            },
        )

        # Store 2: Overlapping data with different values
        store2 = TopicStore(
            topics_by_dcid={
                "topic/health": TopicVariables(
                    topic_dcid="topic/health",
                    topic_name="Health & Wellness",  # Different name
                    variables=[
                        "sv/health_var1",
                        "sv/health_var2",
                    ],  # Additional variable
                    member_topics=["topic/mental_health"],  # Additional member topic
                )
            },
            all_variables={"sv/health_var1", "sv/health_var2"},
            dcid_to_name={
                "topic/health": "Health & Wellness",  # Different name
                "sv/health_var1": "Health Variable 1",
                "sv/health_var2": "Health Variable 2",  # New variable
            },
        )

        result = store1.merge(store2)

        # Verify merged topics (first store's data prevailed)
        expected_topics = {"topic/health"}
        assert set(result.topics_by_dcid.keys()) == expected_topics

        # Verify topic content from first store prevailed
        expected_health_topic = TopicVariables(
            topic_dcid="topic/health",
            topic_name="Health",  # First store's name
            variables=["sv/health_var1"],  # First store's variables only
            member_topics=[],  # First store's member topics
        )
        assert result.topics_by_dcid["topic/health"] == expected_health_topic

        # Verify variables were merged (both stores' variables)
        expected_variables = {"sv/health_var1", "sv/health_var2"}
        assert result.all_variables == expected_variables

        # Verify names from first store prevailed for overlapping keys
        expected_names = {
            "topic/health": "Health",  # First store's name
            "sv/health_var1": "Health Variable 1",  # First store's name
            "sv/health_var2": "Health Variable 2",  # Second store's new variable
        }
        assert result.dcid_to_name == expected_names


class TestReadTopicCaches:
    """Test cases for reading and merging multiple topic cache files."""

    def test_read_topic_caches_multiple_files(self, tmp_path):
        """Test reading multiple cache files and merging them."""
        cache1_data = {
            "nodes": [
                {
                    "dcid": ["topic/health"],
                    "name": ["Health"],
                    "typeOf": ["Topic"],
                    "memberList": [],
                    "relevantVariableList": ["sv/health_var1"],
                }
            ]
        }

        cache2_data = {
            "nodes": [
                {
                    "dcid": ["topic/economy"],
                    "name": ["Economy"],
                    "typeOf": ["Topic"],
                    "memberList": [],
                    "relevantVariableList": ["sv/econ_var1"],
                }
            ]
        }

        # Create cache files
        cache1 = tmp_path / "cache1.json"
        cache2 = tmp_path / "cache2.json"

        with cache1.open("w") as f:
            json.dump(cache1_data, f)

        with cache2.open("w") as f:
            json.dump(cache2_data, f)

        result = read_topic_caches([cache1, cache2])

        # Verify merged results
        expected_topics = {"topic/health", "topic/economy"}
        assert set(result.topics_by_dcid.keys()) == expected_topics

        expected_variables = {"sv/health_var1", "sv/econ_var1"}
        assert result.all_variables == expected_variables
