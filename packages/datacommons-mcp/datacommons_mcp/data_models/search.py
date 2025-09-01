"""
Data models for search functionality.

This module defines Pydantic models for search operations including search tasks
and results used in the search_indicators functionality.
"""

from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    """Enumeration of search modes for the search_indicators tool."""
    
    BROWSE = "browse"
    LOOKUP = "lookup"


# Type alias for use in function signatures and validation
SearchModeType = Literal["browse", "lookup"]


class SearchTask(BaseModel):
    """Represents a single search task with query and place filters."""
    
    query: str = Field(..., description="The search query string")
    place_dcids: list[str] = Field(default_factory=list, description="List of place DCIDs to filter by")


class SearchVariable(BaseModel):
    """Represents a variable object in search results."""
    
    dcid: str = Field(..., description="Variable DCID")
    places_with_data: list[str] = Field(default_factory=list, description="Place DCIDs where data exists")


class SearchTopic(BaseModel):
    """Represents a topic object in search results."""
    
    dcid: str = Field(..., description="Topic DCID")
    member_topics: list[str] = Field(default_factory=list, description="Direct member topic DCIDs")
    member_variables: list[str] = Field(default_factory=list, description="Direct member variable DCIDs")
    places_with_data: list[str] | None = Field(None, description="Place DCIDs where data exists (if place filtering was performed)")


class SearchResult(BaseModel):
    """Represents intermediate results from DCClient with efficient DCID-based storage."""
    
    topics: dict[str, SearchTopic] = Field(default_factory=dict, description="Map of topic DCID to SearchTopic")
    variables: dict[str, SearchVariable] = Field(default_factory=dict, description="Map of variable DCID to SearchVariable")


class SearchResponse(BaseModel):
    """Unified response model for search operations.
    
    Kept minimal to be mindful of LLM context window size.
    """
    
    # Core data - unified structure for both modes
    topics: list[SearchTopic] | None = Field(None, description="List of topic objects (browse mode only)")
    variables: list[SearchVariable] = Field(..., description="List of variable objects with dcid and places_with_data")
    lookups: dict[str, str] = Field(default_factory=dict, description="DCID to name mappings")
    
    # Minimal metadata for context
    status: str = Field(default="SUCCESS", description="Status of the search operation")
