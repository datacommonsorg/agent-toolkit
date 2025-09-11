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
import re
from datetime import datetime
from enum import Enum
from functools import lru_cache
from typing import Any

from datacommons_client.endpoints.response import ObservationResponse
from datacommons_client.models.observation import Observation, OrderedFacet
from datacommons_mcp.exceptions import (
    InvalidDateFormatError,
    InvalidDateRangeError,
)
from dateutil.parser import parse
from pydantic import BaseModel, Field, field_validator

# Wrapper to rename datacommons_client ObservationResponse to avoid confusion.
ObservationApiResponse = ObservationResponse

STANDARDIZED_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_DATE = datetime(1970, 1, 1)  # UTC start date


class ObservationDateType(str, Enum):
    """Enumeration for special date strings in observation queries."""

    ALL = "all"
    LATEST = "latest"
    RANGE = "range"


# Regex to validate that a string is in YYYY, YYYY-MM, or YYYY-MM-DD format.
DATE_FORMAT_REGEX = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")


class ObservationDate(BaseModel):
    date: str

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validates that the date is a known constant or a valid date format."""
        if v.lower() in [member.value for member in ObservationDateType]:
            return v.lower()

        if not DATE_FORMAT_REGEX.match(v):
            raise InvalidDateFormatError(
                f"Date string '{v}' is not one of the valid constants nor in YYYY, YYYY-MM, or YYYY-MM-DD format."
            )

        try:
            # After regex validation, parse to catch invalid values like '2023-99'.
            ObservationDate.parse_date(v)
            return v
        except ValueError as e:
            # This will catch errors from dateutil.parser for invalid dates.
            raise InvalidDateFormatError(
                f"Date string '{v}' contains an invalid value"
            ) from e

    @staticmethod
    def parse_date(date_str: str) -> datetime:
        try:
            return parse(date_str, default=DEFAULT_DATE)
        except ValueError as e:
            raise InvalidDateFormatError(f"for date '{date_str}': {e}") from e


class DateRange(BaseModel):
    "Accepted formats: YYYY or YYYY-MM or YYYY-MM-DD"

    start_date: datetime | None = None
    end_date: datetime | None = None

    def __init__(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        **kwargs: dict[str, Any],
    ) -> None:
        """Initializes and validates the date range from string inputs."""
        super().__init__(**kwargs)

        range_start = DateRange.get_start_date(start_date) if start_date else None
        range_end = DateRange.get_end_date(end_date) if end_date else None

        if range_start and range_end and range_start > range_end:
            raise InvalidDateRangeError(
                f"start_date '{start_date}' cannot be after end_date '{end_date}'"
            )

        self.start_date = range_start
        self.end_date = range_end

    @property
    def start_date_str(self) -> str | None:
        """Returns the start_date as a standardized 'YYYY-MM-DD' string, or None."""
        if not self.start_date:
            return None
        return self.start_date.strftime(STANDARDIZED_DATE_FORMAT)

    @property
    def end_date_str(self) -> str | None:
        """Returns the end_date as a standardized 'YYYY-MM-DD' string, or None."""
        if not self.end_date:
            return None
        return self.end_date.strftime(STANDARDIZED_DATE_FORMAT)

    @staticmethod
    def get_start_date(date_str: str) -> datetime:
        """
        Converts a partial date string into a full start date.
        Caches results to avoid re-calculating for the same input string.

        Examples:
            >>> DateRange.parse_interval("2022")
            ('2022-01-01')

            >>> DateRange.parse_interval("2023-05")
            ('2023-05-01')

            >>> DateRange.parse_interval("2024-01-15")
            ('2024-01-15')

        Raises:
            InvalidDateFormatError: If the date string format is invalid.
        """
        return ObservationDate.parse_date(date_str)

    @staticmethod
    def get_end_date(date_str: str) -> datetime:
        """
        Converts a partial date string into a full (start, end) date tuple.
        Caches results to avoid re-calculating for the same input string.

        Examples:
            >>> DateRange.parse_interval("2022")
            ('2022-12-31')

            >>> DateRange.parse_interval("2023-05")
            ('2023-05-31')

            >>> DateRange.parse_interval("2024-01-15")
            ('2024-01-15')

        Raises:
            InvalidDateFormatError: If the date string format is invalid.
        """
        try:
            parts = date_str.split("-")
            num_parts = len(parts)

            if num_parts == 1:
                year = int(parts[0])
                return datetime(year=year, month=12, day=31)

            if num_parts == 2:
                year, month = map(int, parts)
                # This will raise ValueError for an invalid month.
                datetime(year=year, month=month, day=1)
                _, last_day = calendar.monthrange(year, month)
                return datetime(year=year, month=month, day=last_day)

            if num_parts == 3:
                year, month, day = map(int, parts)
                # This will raise ValueError for an invalid year, month, or day.
                return datetime(year=year, month=month, day=day)

            # If we reach here, the number of parts is not 1, 2, or 3.
            raise ValueError(
                "Date string must be in YYYY, YYYY-MM, or YYYY-MM-DD format."
            )

        except ValueError as e:
            # Catch multiple potential errors and raise a single, clear custom exception.
            raise InvalidDateFormatError(f"for date '{date_str}': {e}") from e

    @staticmethod
    @lru_cache(maxsize=128)
    def parse_interval(date_str: str) -> tuple[datetime, datetime]:
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
        return DateRange.get_start_date(date_str), DateRange.get_end_date(date_str)


class ObservationRequest(BaseModel):
    variable_dcid: str
    place_dcid: str
    child_place_type_dcid: str | None = None
    source_ids: list[str] | None = None
    date_type: ObservationDateType = None
    date_filter: DateRange | None = None
    child_place_type: str | None = None


class SourceProcessingResult(BaseModel):
    """Intermediate model for holding the results of source processing."""

    class ProcessedPlaceData(BaseModel):
        """
        Holds the filtered observations and facet data for a single place.
        This is a private inner class as it's only used within SourceProcessingResult.
        """

        facet: OrderedFacet
        observations: list[Observation]

    primary_source_id: str | None = Field(
        default=None,
        description="The DCID of the selected primary data source (facet).",
    )
    alternative_source_counts: dict[str, int] = Field(
        default_factory=dict,
        description="A map of alternative source DCIDs to the number of places they have data for.",
    )
    processed_data_by_place: dict[str, "ProcessedPlaceData"] = Field(
        default_factory=dict,
        description="A map where keys are place DCIDs and values contain the facet and filtered observations for that place.",
    )

    @property
    def has_data(self) -> bool:
        """Returns True if any data was processed, False otherwise."""
        return self.primary_source_id is not None or self.processed_data_by_place


TimeSeriesPoint = tuple[str, float]  # [date, value]


class ToolResponseBaseModel(BaseModel):
    """A base model to configure all tool responses to exclude None values."""

    model_config = {"populate_by_name": True}


class Node(ToolResponseBaseModel):
    """Represents a Data Commons node, with an optional name, type, and dcid."""

    dcid: str | None = None
    name: str | None = None
    type_of: list[str] | None = Field(default=None, alias="typeOf")


class FacetMetadata(BaseModel):
    """Represents the static metadata for a data source."""

    source_id: str
    import_name: str | None = Field(default=None, alias="importName")
    measurement_method: str | None = Field(default=None, alias="measurementMethod")
    observation_period: str | None = Field(default=None, alias="observationPeriod")
    provenance_url: str | None = Field(default=None, alias="provenanceUrl")
    unit: str | None = None


class AlternativeSource(FacetMetadata):
    """Represents metadata for an alternative data source."""

    places_found_count: int | None = Field(
        default=None,
        description=(
            "The number of places within the current API response for which this"
            " alternative source has data. Used only in child-place type responses."
        ),
    )


class PlaceObservation(ToolResponseBaseModel):
    """Contains all observation data for a single place."""

    place: Node
    time_series: list[TimeSeriesPoint] = Field(
        default_factory=list,
        description="List of observation tuples with the format (date, value)",
    )


class ObservationToolResponse(ToolResponseBaseModel):
    """The response from the get_observations tool.

    It contains observation data organized as a list of places. To save tokens,
    source information is normalized into a top-level `source_info` dictionary.
    """

    variable: Node

    resolved_parent_place: Node | None = Field(
        default=None,
        description=(
            "The parent place that was resolved from the request, if a hierarchical"
            " query was made. This confirms how the tool interpreted the `place_name`."
        ),
    )

    child_place_type: str | None = Field(
        default=None,
        description=(
            "The common place type for all observations in the response (e.g., 'State', 'County', 'AdministrativeArea2'). "
            "This is present when a hierarchical query was made."
        ),
    )

    place_observations: list[PlaceObservation] = Field(
        default_factory=list,
        description="A list of observation data, with one entry per place. This list may be empty if no data is found.",
    )

    source_metadata: FacetMetadata = Field(
        description="Information about the primary data source used for the observations."
    )
    alternative_sources: list[AlternativeSource] = Field(
        default_factory=list,
        description="A list of other available data sources for the same variable and places.",
    )
