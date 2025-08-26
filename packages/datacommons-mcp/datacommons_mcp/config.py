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
Configuration module for Data Commons clients.
"""

import os
from dotenv import load_dotenv

from .data_models.enums import SearchScope
from .data_models.config import BaseDCConfig, CustomDCConfig, DCConfig

# Environment variable names
DC_API_KEY_ENV = "DC_API_KEY"
DC_TYPE_ENV = "DC_TYPE"
DC_BASE_URL_ENV = "DC_BASE_URL"
DC_SEARCH_SCOPE_ENV = "DC_SEARCH_SCOPE"
DC_BASE_INDEX_ENV = "DC_BASE_INDEX"
DC_CUSTOM_INDEX_ENV = "DC_CUSTOM_INDEX"
DC_ROOT_TOPIC_DCIDS_ENV = "DC_ROOT_TOPIC_DCIDS"
DC_SV_SEARCH_BASE_URL_ENV = "DC_SV_SEARCH_BASE_URL"
DC_TOPIC_CACHE_PATH_ENV = "DC_TOPIC_CACHE_PATH"


def _load_env_file() -> None:
    """Load .env file if present in the current directory."""
    load_dotenv()


def _parse_csv(value: str) -> list[str] | None:
    """
    Parse a comma-separated value into a list of strings.
    
    Args:
        value: The comma-separated value to parse
        
    Returns:
        List of strings if value is not empty, None otherwise
    """
    if not value or not value.strip():
        return None
    
    # Split by comma and strip whitespace from each item
    items = [item.strip() for item in value.split(",")]
    # Filter out empty items
    return [item for item in items if item]





def get_dc_config() -> DCConfig:
    """
    Get Data Commons configuration from environment variables.
    
    Returns:
        DCConfig object containing the configuration
        
    Raises:
        ValueError: If required configuration is missing or invalid
    """
    # Load .env file if present
    _load_env_file()
    
    # Get required configuration
    api_key = os.getenv(DC_API_KEY_ENV)
    if not api_key:
        raise ValueError(f"{DC_API_KEY_ENV} environment variable is required")
    
    dc_type = os.getenv(DC_TYPE_ENV)
    if not dc_type:
        raise ValueError(f"{DC_TYPE_ENV} environment variable is required")
    
    # Get optional configuration
    base_url = os.getenv(DC_BASE_URL_ENV)
    search_scope = os.getenv(DC_SEARCH_SCOPE_ENV)
    base_index = os.getenv(DC_BASE_INDEX_ENV)
    custom_index = os.getenv(DC_CUSTOM_INDEX_ENV)
    root_topic_dcids = os.getenv(DC_ROOT_TOPIC_DCIDS_ENV)
    sv_search_base_url = os.getenv(DC_SV_SEARCH_BASE_URL_ENV)
    topic_cache_path = os.getenv(DC_TOPIC_CACHE_PATH_ENV)
    
    # Parse comma-separated values
    root_topic_dcids_list = _parse_csv(root_topic_dcids) if root_topic_dcids else None
    
    # Create appropriate configuration object
    if dc_type == "custom":
        if not base_url:
            raise ValueError(f"{DC_BASE_URL_ENV} is required when {DC_TYPE_ENV}=custom")
        
        # Build config data, only including fields that are provided
        config_data = {
            "dc_type": dc_type,
            "api_key": api_key,
            "base_url": base_url,
        }
        
        if search_scope:
            config_data["search_scope"] = SearchScope(search_scope)
        if base_index:
            config_data["base_index"] = base_index
        if custom_index:
            config_data["custom_index"] = custom_index
        if root_topic_dcids_list:
            config_data["root_topic_dcids"] = root_topic_dcids_list
        
        return CustomDCConfig.model_validate(config_data)
    else:
        # Build config data, only including fields that are provided
        config_data = {
            "dc_type": dc_type,
            "api_key": api_key,
        }
        
        if sv_search_base_url:
            config_data["sv_search_base_url"] = sv_search_base_url
        if base_index:
            config_data["base_index"] = base_index
        if topic_cache_path:
            config_data["topic_cache_path"] = topic_cache_path
        
        return BaseDCConfig.model_validate(config_data)
