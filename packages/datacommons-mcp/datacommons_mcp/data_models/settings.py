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
Pydantic settings for configuring the MCP server.
"""

import os
from typing import Union, Literal
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from .enums import SearchScope

_MODEL_CONFIG = {
    "env_file": ".env",
    "extra": "ignore"
}


class DCSettingsSelector(BaseSettings):
    """Settings selector to determine DC type from environment."""
    
    model_config = _MODEL_CONFIG
    
    dc_type: Literal["base", "custom"] = Field(
        default="base",
        alias="DC_TYPE",
        description="Type of Data Commons"
    )


class BaseDCSettings(BaseSettings):
    """Settings for base Data Commons instance."""
    
    model_config = _MODEL_CONFIG
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    dc_type: Literal["base"] = Field(
        default="base",
        alias="DC_TYPE",
        description="Type of Data Commons (must be 'base')"
    )
    api_key: str = Field(
        alias="DC_API_KEY",
        description="API key for Data Commons"
    )
    sv_search_base_url: str = Field(
        default="https://datacommons.org",
        alias="DC_SV_SEARCH_BASE_URL",
        description="Search base URL for base DC"
    )
    base_index: str = Field(
        default="base_uae_mem",
        alias="DC_BASE_INDEX",
        description="Search index for base DC"
    )
    topic_cache_path: str | None = Field(
        default=None,
        alias="DC_TOPIC_CACHE_PATH",
        description="Path to topic cache file"
    )


class CustomDCSettings(BaseSettings):
    """Settings for custom Data Commons instance."""
    
    model_config = _MODEL_CONFIG
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    dc_type: Literal["custom"] = Field(
        default="custom",
        alias="DC_TYPE",
        description="Type of Data Commons (must be 'custom')"
    )
    api_key: str = Field(
        alias="DC_API_KEY",
        description="API key for Data Commons"
    )
    custom_dc_url: str = Field(
        alias="CUSTOM_DC_URL",
        description="Base URL for custom Data Commons instance"
    )
    api_base_url: str | None = Field(
        default=None,
        alias="DC_API_BASE_URL",
        description="API base URL (computed from base_url if not provided)"
    )
    search_scope: SearchScope = Field(
        default=SearchScope.BASE_AND_CUSTOM,
        alias="DC_SEARCH_SCOPE",
        description="Search scope for queries"
    )
    base_index: str = Field(
        default="medium_ft",
        alias="DC_BASE_INDEX",
        description="Search index for base DC"
    )
    custom_index: str = Field(
        default="user_all_minilm_mem",
        alias="DC_CUSTOM_INDEX",
        description="Search index for custom DC"
    )
    root_topic_dcids: list[str] | None = Field(
        default=None,
        alias="DC_ROOT_TOPIC_DCIDS",
        description="List of root topic DCIDs"
    )
    
    @field_validator('root_topic_dcids', mode='before')
    @classmethod
    def parse_root_topic_dcids(cls, v):
        """Parse comma-separated string into list of strings."""
        if isinstance(v, str):
            if not v.strip():
                return None
            # Split by comma and strip whitespace from each item
            items = [item.strip() for item in v.split(",")]
            # Filter out empty items
            return [item for item in items if item]
        return v
    
    @model_validator(mode='after')
    def compute_api_base_url(self) -> 'CustomDCSettings':
        """Compute api_base_url from custom_dc_url if not provided."""
        if self.api_base_url is None:
            self.api_base_url = self.custom_dc_url.rstrip("/") + "/core/api/v2/"
        return self


# Union type for both settings
DCSettings = Union[BaseDCSettings, CustomDCSettings]
