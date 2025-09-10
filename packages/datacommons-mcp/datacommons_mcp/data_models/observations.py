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
from pydantic import BaseModel, Field, field_validator, model_validator

# Wrapper to rename datacommons_client ObservationResponse to avoid confusion.
ObservationApiResponse = ObservationResponse

STANDARDIZED_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_DATE = datetime(1970, 1, 1)  # UTC start date


class ObservationDateType(str, Enum):
    """Enumeration for special date strings in observation queries."""

    ALL = "all"
    LATEST = "latest"
    RANGE = "range"


class ObservationDate(BaseModel):
    date: str

    @field_validator("date")
    def validate_date_format(cls, v: str) -> str:  # noqa: B902,N805
        """Validates that the date is a known constant or a valid date format."""
        if v.lower() in [member.value for member in ObservationDateType]:
            return v.lower()
        try:
            # Use the existing robust parsing logic from DateRange
            DateRange.parse_interval(v)
            return v
        except InvalidDateFormatError:
            raise InvalidDateFormatError(
                f"Date string '{v}' is not a valid constant "
                f"{[member.value for member in ObservationDateType]} "
                f"or in YYYY, YYYY-MM, or YYYY-MM-DD format."
            ) from None


class DateRange(BaseModel):
    "Accepted formats: YYYY or YYYY-MM or YYYY-MM-DD"

    start_date: str | None
    end_date: str | None

    @staticmethod
    def get_standardized_date(date_str: str) -> datetime:
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            return parse(date_str, default=DEFAULT_DATE)

    @staticmethod
    def get_standardized_date_str(date_str: str) -> str:
        return DateRange.get_standardized_date(date_str).strftime(
            STANDARDIZED_DATE_FORMAT
        )

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
                    STANDARDIZED_DATE_FORMAT
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

        if original_start:
            range_start, _ = DateRange.parse_interval(original_start)
        else:
            range_start = None

        if original_end:
            _, range_end = DateRange.parse_interval(original_end)
        else:
            range_end = None

        if range_start and range_end and range_start > range_end:
            raise InvalidDateRangeError(
                f"start_date '{original_start}' cannot be after end_date '{original_end}'"
            )
        self.start_date, self.end_date = range_start, range_end
        return self


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

    def model_dump(
        self,
        **kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        """Override model_dump to exclude None by default."""
        # We call the super() method (the original BaseModel dump)
        # passing our new default for exclude_none.
        return super().model_dump(exclude_none=True, **kwargs)

    def model_dump_json(
        self,  # Changed default to True
        **kwargs: dict[str, Any],
    ) -> str:
        """Override model_dump_json to exclude None by default."""
        # Same logic for the JSON-specific method
        return super().model_dump_json(exclude_none=True, **kwargs)


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

    place_count: int | None = Field(
        default=None,
        description=(
            "The number of places within the current API response for which this"
            " alternative source has data."
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

    variable_dcid: str

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
            "The common place type for all observations in the response (e.g., 'State', 'County'). "
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
