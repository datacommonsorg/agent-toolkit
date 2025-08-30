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
"""
Enums for data modeling.
Contains enums used for modeling data constraints and types.
"""

from enum import Enum


class SearchScope(Enum):
    """Enum for controlling search scope in Data Commons queries."""

    CUSTOM_ONLY = "custom_only"
    BASE_ONLY = "base_only"
    BASE_AND_CUSTOM = "base_and_custom"
