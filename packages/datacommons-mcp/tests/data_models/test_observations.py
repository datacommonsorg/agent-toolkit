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

from datetime import datetime

import pytest

# Import the classes and functions to be tested
from datacommons_mcp.data_models.observations import (
    DateRange,
    ObservationDate,
)
from datacommons_mcp.exceptions import InvalidDateFormatError, InvalidDateRangeError
from pydantic import ValidationError


class TestObservationDate:
    def test_valid_constants(self):
        """Tests that valid constants are accepted and normalized."""
        assert ObservationDate(date="all").date == "all"
        assert ObservationDate(date="latest").date == "latest"
        assert ObservationDate(date="range").date == "range"
        # Test case-insensitivity
        assert ObservationDate(date="ALL").date == "all"
        assert ObservationDate(date="LaTeSt").date == "latest"

    def test_valid_date_formats(self):
        """Tests that valid date string formats are accepted."""
        assert ObservationDate(date="2023").date == "2023"
        assert ObservationDate(date="2023-05").date == "2023-05"
        assert ObservationDate(date="2023-05-15").date == "2023-05-15"

    def test_invalid_constant_raises_error(self):
        """Tests that an invalid constant string raises an error."""
        with pytest.raises(
            ValidationError,
            match="Date string 'invalid_string' is not one of the valid constants",
        ):
            ObservationDate(date="invalid_string")

    def test_invalid_date_format_raises_error(self):
        """Tests that an invalid date format string raises an error."""
        with pytest.raises(
            ValidationError,
            match="Date string '2023-13' contains an invalid value.",
        ):
            ObservationDate(date="2023-13")  # Invalid month

        with pytest.raises(
            ValidationError,
            match="Date string '12-2025' is not one of the valid constants",
        ):
            ObservationDate(date="12-2025")  # Invalid month-year order

    # Tests for the static method parse_date
    def test_parse_date_valid(self):
        """Tests that parse_date correctly parses valid date strings."""
        assert ObservationDate.parse_date("2023-07-15") == datetime(2023, 7, 15)

        # Test with only year, use default values for month and day
        assert ObservationDate.parse_date("2022") == datetime(2022, 1, 1)

    def test_parse_date_invalid(self):
        """Tests that parse_date raises an error for invalid date strings."""
        with pytest.raises(InvalidDateFormatError, match="for date 'not-a-date'"):
            ObservationDate.parse_date("not-a-date")


class TestDateRange:
    # Tests for the model constructor
    def test_constructor_valid_range(self):
        """Tests that the model validator accepts valid date ranges."""
        # YYYY to full year
        dr1 = DateRange(start_date="2022", end_date="2022")
        assert dr1.start_date_str == "2022-01-01"
        assert dr1.end_date_str == "2022-12-31"

        # YYYY-MM to full month
        dr2 = DateRange(start_date="2023-02", end_date="2024-02")
        assert dr2.start_date_str == "2023-02-01"
        assert dr2.end_date_str == "2024-02-29"  # Leap year

        # Mixed formats
        dr3 = DateRange(start_date="2023", end_date="2023-07-15")
        assert dr3.start_date_str == "2023-01-01"
        assert dr3.end_date_str == "2023-07-15"

    def test_constructor_invalid_range_raises_error(self):
        """Tests that an end_date before a start_date raises an error."""
        with pytest.raises(
            InvalidDateRangeError,
            match="start_date '2023' cannot be after end_date '2022'",
        ):
            DateRange(start_date="2023", end_date="2022")

        with pytest.raises(
            InvalidDateRangeError,
            match="start_date '2023-02' cannot be after end_date '2023-01'",
        ):
            DateRange(start_date="2023-02", end_date="2023-01")

    def test_constructor_invalid_format_raises_error(self):
        """Tests that an invalid date format string raises an error through the validator."""
        with pytest.raises(InvalidDateFormatError, match="for date 'not-a-date'"):
            DateRange(start_date="not-a-date", end_date="2023")

    # Tests for the static method get_start_date
    def test_get_start_date(self):
        """Tests that get_start_date correctly normalizes various date formats."""
        assert DateRange.get_start_date("2023") == datetime(2023, 1, 1)
        assert DateRange.get_start_date("2023-05") == datetime(2023, 5, 1)
        assert DateRange.get_start_date("2023-07-15") == datetime(2023, 7, 15)
        with pytest.raises(InvalidDateFormatError, match="for date 'not-a-date'"):
            DateRange.get_start_date("not-a-date")

    # Tests for the static method get_end_date
    def test_get_end_date(self):
        """Tests that get_end_date correctly finds the end of a date period."""
        assert DateRange.get_end_date("2023") == datetime(2023, 12, 31)
        assert DateRange.get_end_date("2023-02") == datetime(
            2023, 2, 28
        )  # Non-leap year
        assert DateRange.get_end_date("2024-02") == datetime(2024, 2, 29)  # Leap year
        assert DateRange.get_end_date("2023-07-15") == datetime(2023, 7, 15)
        with pytest.raises(InvalidDateFormatError, match="for date '2023-13'"):
            DateRange.get_end_date("2023-13")  # Invalid month

    # Note: parse_interval is implicitly tested by get_start_date and get_end_date
