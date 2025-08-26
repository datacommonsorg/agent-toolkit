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
Pydantic models for configuring the MCP server.
"""

from typing import Union, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

from .enums import SearchScope


class BaseDCConfig(BaseModel):
    """Configuration for base Data Commons instance."""
    
    dc_type: Literal["base"] = Field(description="Type of Data Commons (must be 'base')")
    api_key: str = Field(description="API key for Data Commons")
    sv_search_base_url: str = Field(
        default="https://datacommons.org",
        description="Search base URL for base DC"
    )
    base_index: str = Field(
        default="base_uae_mem",
        description="Search index for base DC"
    )
    topic_cache_path: str | None = Field(
        default=None,
        description="Path to topic cache file"
    )
    



class CustomDCConfig(BaseModel):
    """Configuration for custom Data Commons instance."""
    
    dc_type: Literal["custom"] = Field(description="Type of Data Commons (must be 'custom')")
    api_key: str = Field(description="API key for Data Commons")
    base_url: str = Field(description="Base URL for custom Data Commons instance")
    api_base_url: str | None = Field(
        default=None,
        description="API base URL (computed from base_url if not provided)"
    )
    search_scope: SearchScope = Field(
        default=SearchScope.BASE_AND_CUSTOM,
        description="Search scope for queries"
    )
    base_index: str = Field(
        default="medium_ft",
        description="Search index for base DC"
    )
    custom_index: str = Field(
        default="user_all_minilm_mem",
        description="Search index for custom DC"
    )
    root_topic_dcids: list[str] | None = Field(
        default=None,
        description="List of root topic DCIDs"
    )
    

    

    
    @model_validator(mode='after')
    def compute_api_base_url(self) -> 'CustomDCConfig':
        """Compute api_base_url from base_url if not provided."""
        if self.api_base_url is None:
            self.api_base_url = self.base_url.rstrip("/") + "/core/api/v2/"
        return self


# Union type for both configurations
DCConfig = Union[BaseDCConfig, CustomDCConfig]
