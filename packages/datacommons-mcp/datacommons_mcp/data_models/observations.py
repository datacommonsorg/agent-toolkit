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


from datacommons_client.endpoints.response import ObservationResponse
from datacommons_client.models.observation import Facet, Observation, ObservationDate
from datacommons_mcp.exceptions import (
    InvalidDateRangeError,
)
from datacommons_mcp.utils import parse_date_interval
from pydantic import BaseModel, Field, model_validator


class ObservationPeriod(ObservationDate):
    """Wrapper to rename datacommons_client object to avoid confusion."""


class DateRange(BaseModel):
    "Accepted formats: YYYY or YYYY-MM or YYYY-MM-DD"

    start_date: str
    end_date: str

    @model_validator(mode="after")
    def validate_and_normalize_dates(self) -> "DateRange":
        """
        Validates that start_date is not after end_date and normalizes
        both to the full YYYY-MM-DD format representing the interval.
        """
        # The fields are guaranteed to be present because of the validator mode.
        # Keep original values for potential error messages
        original_start = self.start_date
        original_end = self.end_date

        range_start, _ = parse_date_interval(original_start)
        _, range_end = parse_date_interval(original_end)

        if range_start > range_end:
            raise InvalidDateRangeError(
                f"start_date '{original_start}' cannot be after end_date '{original_end}'"
            )
        self.start_date, self.end_date = range_start, range_end
        return self


class ObservationToolRequest(BaseModel):
    variable_dcid: str
    place_dcid: str
    child_place_type_dcid: str | None = None
    facet_ids: list[str] | None = None
    observation_period: ObservationPeriod | str = None
    date_filter: DateRange | None = None
    child_place_type: str | None = None


class SourceMetadata(Facet):
    dc_client_id: str
    earliest_date: str
    latest_date: str
    total_observations: int


class VariableSeries(BaseModel):
    variable_dcid: str
    source_metadata: SourceMetadata
    observations: list[Observation]
    alternative_sources: list[SourceMetadata] = Field(default_factory=list)


class PlaceData(BaseModel):
    place_dcid: str = Field(default_factory=str)
    place_name: str = Field(default_factory=str)
    variable_series: dict[str, VariableSeries] = Field(default_factory=dict)


class ObservationApiResponse(ObservationResponse):
    """Wrapper to rename DC Client ObservationResponse to avoid confusion."""


class ObservationToolResponse(BaseModel):
    place_data: dict[str, PlaceData] = Field(default_factory=dict)
