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

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from .enums import SearchScope

_MODEL_CONFIG = {"env_file": ".env", "extra": "ignore"}


class DCSettingsSelector(BaseSettings):
    """Settings selector to determine DC type from environment."""

    model_config = _MODEL_CONFIG

    dc_type: Literal["base", "custom"] = Field(
        default="base", alias="DC_TYPE", description="Type of Data Commons"
    )


class DCSettings(BaseSettings):
    """Settings for base Data Commons instance."""

    model_config = _MODEL_CONFIG

    # API key validation happens in cli.py. Default key in settings is empty to handle skip
    # validation scenarios where api key issues should be handled at tool call time instead of
    # server start up.
    api_key: str = Field(default="",
                         alias="DC_API_KEY",
                         description="API key for Data Commons")

    use_search_indicators_endpoint: bool = Field(
        default=True,
        alias="DC_USE_SEARCH_INDICATORS_ENDPOINT",
        description=(
            "Toggles between search-indicators and search-vector endpoint."),
    )


class BaseDCSettings(DCSettings):
    """Settings for base Data Commons instance."""

    def __init__(self, **kwargs: dict[str, Any]) -> None:
        super().__init__(**kwargs)

    dc_type: Literal["base"] = Field(
        default="base",
        alias="DC_TYPE",
        description="Type of Data Commons (must be 'base')",
    )
    sv_search_base_url: str = Field(
        default="https://datacommons.org",
        alias="DC_SV_SEARCH_BASE_URL",
        description="Search base URL for base DC",
    )
    base_index: str = Field(
        default="base_uae_mem",
        alias="DC_BASE_INDEX",
        description="Search index for base DC",
    )
    topic_cache_paths: list[str] | None = Field(
        default=None,
        alias="DC_TOPIC_CACHE_PATHS",
        description="Paths to topic cache files",
    )

    base_root_topic_dcids: list[str] | None = Field(
        default=["dc/topic/Root", "dc/topic/sdg"],
        alias="DC_BASE_ROOT_TOPIC_DCIDS",
        description="List of root topic DCIDs for base DC",
    )

    @field_validator("topic_cache_paths", "base_root_topic_dcids", mode="before")
    @classmethod
    def parse_list_like_parameter(cls, v: str) -> list[str] | None:
        return _parse_list_like_parameter(v)


class CustomDCSettings(DCSettings):
    """Settings for custom Data Commons instance."""

    model_config = _MODEL_CONFIG

    def __init__(self, **kwargs: dict[str, Any]) -> None:
        super().__init__(**kwargs)

    dc_type: Literal["custom"] = Field(
        default="custom",
        alias="DC_TYPE",
        description="Type of Data Commons (must be 'custom')",
    )
    custom_dc_url: str = Field(
        alias="CUSTOM_DC_URL", description="Base URL for custom Data Commons instance"
    )
    api_base_url: str | None = Field(
        default=None,
        alias="DC_API_BASE_URL",
        description="API base URL (computed from base_url if not provided)",
    )
    search_scope: SearchScope = Field(
        default=SearchScope.BASE_AND_CUSTOM,
        alias="DC_SEARCH_SCOPE",
        description="Search scope for queries",
    )
    base_index: str = Field(
        default="medium_ft",
        alias="DC_BASE_INDEX",
        description="Search index for base DC",
    )
    custom_index: str = Field(
        default="user_all_minilm_mem",
        alias="DC_CUSTOM_INDEX",
        description="Search index for custom DC",
    )
    root_topic_dcids: list[str] | None = Field(
        default=None,
        alias="DC_ROOT_TOPIC_DCIDS",
        description="List of root topic DCIDs",
    )
    base_root_topic_dcids: list[str] | None = Field(
        default=["dc/topic/Root", "dc/topic/sdg"],
        alias="DC_BASE_ROOT_TOPIC_DCIDS",
        description="List of root topic DCIDs for base DC",
    )
    topic_cache_paths: list[str] | None = Field(
        default=None,
        alias="DC_TOPIC_CACHE_PATHS",
        description="Paths to topic cache files (unlikely to be used but could be useful for local development)",
    )
    # TODO (@jm-rivera): Remove once new endpoint is live.
    place_like_constraints: list[str] | None = Field(
        default=None,
        alias="PLACE_LIKE_CONSTRAINTS",
        description="List of place-like constraintProperties",
    )

    @field_validator(
        "root_topic_dcids",
        "base_root_topic_dcids",
        "place_like_constraints",
        "topic_cache_paths",
        mode="before",
    )
    @classmethod
    def parse_list_like_parameter(cls, v: str) -> list[str] | None:
        return _parse_list_like_parameter(v)

    @model_validator(mode="after")
    def compute_api_base_url(self) -> "CustomDCSettings":
        """Compute api_base_url from custom_dc_url if not provided."""
        if self.api_base_url is None:
            self.api_base_url = self.custom_dc_url.rstrip("/") + "/core/api/v2/"
        return self


def _parse_list_like_parameter(v: Any) -> list[str] | None:  # noqa: ANN401
    """Parse a comma-separated string or a list into a list of strings."""
    if isinstance(v, list):
        return [s for s in (str(item).strip() for item in v) if s]
    if not isinstance(v, str) or not v.strip():
        return None
    # Split by comma and strip whitespace from each item, filtering out empty strings
    return [s for s in (part.strip() for part in v.split(",")) if s]


# Union type for both settings
DCSettings = BaseDCSettings | CustomDCSettings
