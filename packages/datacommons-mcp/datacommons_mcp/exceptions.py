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


class _ErrorStrMixin:
    """A mixin to provide a descriptive __str__ representation for exceptions."""

    def __str__(self) -> str:
        """Returns a string representation of the exception."""
        message = self.args[0] if self.args else ""
        # Prepend the class name to the message for clarity.
        return f"{self.__class__.__name__}: {message}"


class NoDataFoundError(_ErrorStrMixin, LookupError):
    """Raised when a query returns no data for a valid input."""


class DataLookupError(_ErrorStrMixin, LookupError):
    """Raised when there is an error during a data lookup operation."""


class InvalidDateFormatError(_ErrorStrMixin, ValueError):
    """Raised when a date string has an invalid format."""


class InvalidDateRangeError(_ErrorStrMixin, ValueError):
    """Raised when a start date is later than end date for a date range."""
