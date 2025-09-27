"""
Data models for search functionality.

This module defines Pydantic models for search operations including search tasks
and results used in the search_indicators functionality.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class NodeInfo(BaseModel):
    """Represents node information with name and types."""

    name: str = Field(description="Human-readable name of the node")
    type_of: list[str] = Field(
        description="All types of the node (e.g., ['State', 'AdministrativeArea1'])",
        alias="typeOf",
    )


class SearchMode(str, Enum):
    """Enumeration of search modes for the search_indicators tool."""

    BROWSE = "browse"
    LOOKUP = "lookup"


# Type alias for use in function signatures and validation
SearchModeType = Literal["browse", "lookup"]


class SearchTask(BaseModel):
    """Represents a single search task with query and place filters."""

    query: str = Field(description="The search query string")
    place_dcids: list[str] = Field(
        default_factory=list, description="List of place DCIDs to filter by"
    )


class SearchIndicator(BaseModel):
    """Base model for a search indicator, which can be a topic or a variable."""

    dcid: str
    description: str | None = None
    alternate_descriptions: list[str] | None = Field(
        None, description="Alternate descriptions or matched sentences."
    )


class SearchVariable(SearchIndicator):
    """Represents a variable object in search results."""

    places_with_data: list[str] = Field(
        default_factory=list, description="Place DCIDs where data exists"
    )


class SearchTopic(SearchIndicator):
    """Represents a topic object in search results."""

    member_topics: list[str] = Field(
        default_factory=list, description="Direct member topic DCIDs"
    )
    member_variables: list[str] = Field(
        default_factory=list, description="Direct member variable DCIDs"
    )
    places_with_data: list[str] | None = Field(
        None,
        description="Place DCIDs where data exists (if place filtering was performed)",
    )


class SearchResult(BaseModel):
    """Represents intermediate results from DCClient."""

    topics: dict[str, SearchTopic] = Field(
        default_factory=dict, description="Map of topic DCID to SearchTopic"
    )
    variables: dict[str, SearchVariable] = Field(
        default_factory=dict, description="Map of variable DCID to SearchVariable"
    )


class SearchResponse(BaseModel):
    """Unified response model for search operations."""

    topics: list[SearchTopic] | None = Field(
        None, description="List of topic objects (browse mode only)"
    )
    variables: list[SearchVariable] = Field(
        description="List of variable objects with dcid and places_with_data"
    )
    dcid_name_mappings: dict[str, str] = Field(
        default_factory=dict, description="DCID to name mappings"
    )

    status: str = Field(default="SUCCESS", description="Status of the search operation")
