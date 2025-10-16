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
import requests
from datacommons_client.models.observation import Observation
from datacommons_mcp.data_models.observations import DateRange
from datacommons_mcp.exceptions import APIKeyValidationError, InvalidAPIKeyError
from datacommons_mcp.utils import filter_by_date, validate_api_key


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


class TestValidateAPIKey:
    def test_validate_api_key_success(self, requests_mock):
        requests_mock.get(
            "https://api.datacommons.org/v2/node?nodes=geoId/06", status_code=200
        )
        api_key_to_test = "my-test-api-key"
        assert validate_api_key(api_key_to_test) is True
        assert requests_mock.last_request.headers["X-API-Key"] == api_key_to_test

    def test_validate_api_key_no_key(self):
        with pytest.raises(InvalidAPIKeyError, match="DC_API_KEY is not set."):
            validate_api_key(None)

    def test_validate_api_key_invalid(self, requests_mock):
        requests_mock.get(
            "https://api.datacommons.org/v2/node?nodes=geoId/06", status_code=403
        )
        with pytest.raises(InvalidAPIKeyError):
            validate_api_key("invalid_key")

    def test_validate_api_key_network_error(self, requests_mock):
        requests_mock.get(
            "https://api.datacommons.org/v2/node?nodes=geoId/06",
            exc=requests.exceptions.RequestException("Network error"),
        )
        with pytest.raises(APIKeyValidationError):
            validate_api_key("any_key")
