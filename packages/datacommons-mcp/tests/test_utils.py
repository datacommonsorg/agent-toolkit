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

import pytest
from datacommons_client.models.observation import Observation
from datacommons_mcp.data_models.observations import DateRange
from datacommons_mcp.utils import filter_by_date, merge_dicts


class TestFilterByDate:
    @pytest.fixture
    def observations(self):
        return [
            Observation(date="2022", value=1),
            Observation(date="2023-05", value=2),
            Observation(date="2024-01-15", value=3),
            Observation(date="2024-07", value=4),
        ]

    def test_no_filter(self, observations):
        assert len(filter_by_date(observations, None)) == 4

    def test_filter_contains_fully(self, observations):
        date_filter = DateRange(start_date="2023", end_date="2024")
        result = filter_by_date(observations, date_filter)
        assert len(result) == 3
        assert {obs.value for obs in result} == {2, 3, 4}

    def test_filter_partial_overlap_excluded(self, observations):
        # Observation for "2022" (Jan 1 to Dec 31) is not fully contained
        date_filter = DateRange(start_date="2022-06-01", end_date="2023-06-01")
        result = filter_by_date(observations, date_filter)
        assert len(result) == 1
        assert result[0].value == 2  # Only 2023-05 is fully contained

    def test_empty_result(self, observations):
        date_filter = DateRange(start_date="2025", end_date="2026")
        assert len(filter_by_date(observations, date_filter)) == 0


class TestMergeDicts:
    def test_merge_dicts_unions_values(self):
        d1 = {"p1": ["v1", "v2"], "p2": ["v3"]}
        d2 = {"p1": ["v2", "v4"], "p3": ["v5"]}

        merged = merge_dicts([d1, d2])

        # Expect sets with unioned values
        assert merged["p1"] == {"v1", "v2", "v4"}
        assert merged["p2"] == {"v3"}
        assert merged["p3"] == {"v5"}
