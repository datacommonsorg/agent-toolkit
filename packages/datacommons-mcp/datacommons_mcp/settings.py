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
Settings module for Data Commons clients.
"""

from .data_models.settings import BaseDCSettings, CustomDCSettings, DCSettings, DCSettingsSelector


def get_dc_settings() -> DCSettings:
    """
    Get Data Commons settings from environment variables.
    
    Automatically loads from .env file if present.
    
    Returns:
        DCSettings object containing the configuration
        
    Raises:
        ValueError: If required configuration is missing or invalid
    """

    
    # First, determine the DC type using the settings selector
    settings_selector = DCSettingsSelector()
    
    # Create the appropriate settings class based on the type
    if settings_selector.dc_type == "custom":
        return CustomDCSettings()
    else:
        return BaseDCSettings()
