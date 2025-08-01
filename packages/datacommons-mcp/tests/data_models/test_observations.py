import pytest

# Import the classes and functions to be tested
from datacommons_mcp.data_models.observations import DateRange
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
