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

import calendar
from datetime import datetime
from functools import lru_cache

from datacommons_client.endpoints.response import ObservationResponse
from datacommons_client.models.observation import Facet, Observation, ObservationDate
from datacommons_mcp.exceptions import (
    InvalidDateFormatError,
    InvalidDateRangeError,
)
from pydantic import BaseModel, Field, model_validator

# Wrapper to rename datacommons_client object to avoid confusion.
ObservationPeriod = ObservationDate


class DateRange(BaseModel):
    "Accepted formats: YYYY or YYYY-MM or YYYY-MM-DD"

    start_date: str
    end_date: str

    @staticmethod
    @lru_cache(maxsize=128)
    def parse_interval(date_str: str) -> tuple[str, str]:
        """
        Converts a partial date string into a full (start, end) date tuple.
        Caches results to avoid re-calculating for the same input string.

        Examples:
            >>> DateRange.parse_interval("2022")
            ('2022-01-01', '2022-12-31')

            >>> DateRange.parse_interval("2023-05")
            ('2023-05-01', '2023-05-31')

            >>> DateRange.parse_interval("2024-01-15")
            ('2024-01-15', '2024-01-15')

        Raises:
            InvalidDateFormatError: If the date string format is invalid.
        """
        try:
            parts = date_str.split("-")
            num_parts = len(parts)

            if num_parts == 1:
                year = int(parts[0])
                # Validate the year is reasonable, though int() handles non-numerics.
                datetime(year=year, month=1, day=1)
                return f"{year:04d}-01-01", f"{year:04d}-12-31"

            if num_parts == 2:
                year, month = map(int, parts)
                # This will raise ValueError for an invalid month.
                datetime(year=year, month=month, day=1)
                _, last_day = calendar.monthrange(year, month)
                return (
                    f"{year:04d}-{month:02d}-01",
                    f"{year:04d}-{month:02d}-{last_day:02d}",
                )

            if num_parts == 3:
                year, month, day = map(int, parts)
                # This will raise ValueError for an invalid year, month, or day.
                date_str = datetime(year=year, month=month, day=day).strftime(
                    "%Y-%m-%d"
                )
                return date_str, date_str

            # If we reach here, the number of parts is not 1, 2, or 3.
            raise ValueError(
                "Date string must be in YYYY, YYYY-MM, or YYYY-MM-DD format."
            )

        except ValueError as e:
            # Catch multiple potential errors and raise a single, clear custom exception.
            raise InvalidDateFormatError(f"for date '{date_str}': {e}") from e

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

        range_start, _ = DateRange.parse_interval(original_start)
        _, range_end = DateRange.parse_interval(original_end)

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
    facet_id: str
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
    contained_in: list["PlaceData"] = Field(default_factory=list)
    place_types: list[str] = Field(default_factory=list)


class ObservationApiResponse(ObservationResponse):
    """Wrapper to rename DC Client ObservationResponse to avoid confusion."""


class ObservationToolResponse(BaseModel):
    place_data: dict[str, PlaceData] = Field(
        default_factory=dict, description="PlaceData objects keyed by their dcid."
    )
