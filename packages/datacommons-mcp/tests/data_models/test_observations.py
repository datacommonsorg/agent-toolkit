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

# Import the classes and functions to be tested
from datacommons_mcp.data_models.observations import (
    DateRange,
    ObservationDate,
)
from datacommons_mcp.exceptions import InvalidDateFormatError
from pydantic import ValidationError


class TestDateRange:
    def test_valid_range(self):
        """Tests that valid date ranges do not raise errors."""
        try:
            DateRange(start_date="2022", end_date="2023")
            DateRange(start_date="2022-01", end_date="2022-02")
            DateRange(start_date="2022-01-01", end_date="2022-01-01")
        except ValidationError as e:
            pytest.fail(f"DateRange raised ValidationError unexpectedly: {e}")

    def test_invalid_range_raises_error(self):
        """Tests that an end_date before a start_date raises an error."""
        with pytest.raises(
            ValidationError,
            match="InvalidDateRangeError: start_date '2023' cannot be after end_date '2022'",
        ):
            DateRange(start_date="2023", end_date="2022")

        with pytest.raises(
            ValidationError,
            match="InvalidDateRangeError: start_date '2023-02' cannot be after end_date '2023-01'",
        ):
            DateRange(start_date="2023-02", end_date="2023-01")

    def test_invalid_format_raises_error(self):
        """Tests that an invalid date format raises an error."""
        with pytest.raises(
            ValidationError,
            match=r"InvalidDateFormatError: for date '2023-13': month must be in 1..12",
        ):
            DateRange(start_date="2023-13", end_date="2024")

    def test_date_normalization(self):
        """Tests that dates are normalized to the full interval."""
        # YYYY to full year
        dr1 = DateRange(start_date="2022", end_date="2022")
        assert dr1.start_date == "2022-01-01"
        assert dr1.end_date == "2022-12-31"

        # YYYY-MM to full month
        dr2 = DateRange(start_date="2023-02", end_date="2024-02")
        assert dr2.start_date == "2023-02-01"
        assert dr2.end_date == "2024-02-29"  # Leap year

        # Mixed formats
        dr3 = DateRange(start_date="2023", end_date="2023-07-15")
        assert dr3.start_date == "2023-01-01"
        assert dr3.end_date == "2023-07-15"

    # Tests for the static method parse_interval
    def test_parse_interval_yyyy(self):
        assert DateRange.parse_interval("2023") == ("2023-01-01", "2023-12-31")

    def test_parse_interval_yyyymm(self):
        # Non-leap year
        assert DateRange.parse_interval("2023-02") == ("2023-02-01", "2023-02-28")
        # Leap year
        assert DateRange.parse_interval("2024-02") == ("2024-02-01", "2024-02-29")

    def test_parse_interval_yyyymmdd(self):
        assert DateRange.parse_interval("2023-07-15") == ("2023-07-15", "2023-07-15")

    def test_parse_interval_invalid_format(self):
        with pytest.raises(InvalidDateFormatError):
            DateRange.parse_interval("not-a-date")
        with pytest.raises(InvalidDateFormatError):
            DateRange.parse_interval("2023-13-01")  # Invalid month


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
            match=r"Date string 'invalid_string' is not a valid constant",
        ):
            ObservationDate(date="invalid_string")

    def test_invalid_date_format_raises_error(self):
        """Tests that an invalid date format string raises an error."""
        with pytest.raises(
            ValidationError,
            match=r"Date string '2023-13' is not a valid constant",
        ):
            ObservationDate(date="2023-13")  # Invalid month

        with pytest.raises(ValidationError, match=r"Date string '2023/01/01'"):
            ObservationDate(
                date="2023/01/01"
            )  # Invalid format (slashes instead of dashes)
