"""
Data models for search functionality.

This module defines Pydantic models for search operations including search tasks
and results used in the search_indicators functionality.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchTask(BaseModel):
    """Represents a single search task with query and place filters."""
    
    query: str = Field(..., description="The search query string")
    place_dcids: List[str] = Field(default_factory=list, description="List of place DCIDs to filter by")


class SearchResponse(BaseModel):
    """Unified response model for search operations.
    
    Kept minimal to be mindful of LLM context window size.
    """
    
    # Core data - same structure as current functions
    topics: Optional[List[Dict[str, Any]]] = Field(None, description="List of topic objects (browse mode only)")
    variables: Optional[List[Any]] = Field(None, description="List of variables (DCIDs in lookup mode, objects in browse mode)")
    lookups: Dict[str, str] = Field(default_factory=dict, description="DCID to name mappings")
    
    # Minimal metadata for context
    mode: str = Field(..., description="The search mode used: 'browse' or 'lookup'")
    status: str = Field(default="SUCCESS", description="Status of the search operation")
