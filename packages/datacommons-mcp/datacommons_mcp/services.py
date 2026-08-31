# Copyright 2026 Google LLC.
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
Service layer for calling Agent APIs.
"""

from typing import Any

from datacommons_mcp.app import app
from datacommons_mcp.client import AgentAPIClient
from datacommons_mcp.data_models.enums import ObservationDateType


def _get_client() -> AgentAPIClient:
    """Helper to get the initialized AgentAPIClient, raising RuntimeError if not set."""
    if app.client is None:
        raise RuntimeError("Data Commons client is not initialized.")
    return app.client


async def get_observations(
    variable_dcid: str,
    place_dcid: str,
    child_place_type: str | None = None,
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> dict[str, Any]:
    """Fetches single-place or child-place observations via agent/get_observations."""
    client = _get_client()
    if child_place_type:
        entities: dict[str, Any] = {
            "observationAbout": {
                "parent_dcid": place_dcid,
                "child_type": child_place_type,
            }
        }
    else:
        entities = {"observationAbout": [place_dcid]}

    payload = {
        "variable_dcid": variable_dcid,
        "entities": entities,
        "source_override": source_override,
        "date": date,
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
    }
    return await client.post("agent/get_observations", payload)


async def get_multi_entity_observations(
    variable_dcid: str,
    entities: dict[str, list[str]],
    parent_entity_property: str | None = None,
    parent_entity_dcid: str | None = None,
    child_entity_type: str | None = None,
    source_override: str | None = None,
    date: str = ObservationDateType.LATEST.value,
    date_range_start: str | None = None,
    date_range_end: str | None = None,
) -> dict[str, Any]:
    """Fetches multi-entity observations via the Agent API agent/get_observations endpoint."""
    client = _get_client()
    entities_payload: dict[str, Any] = dict(entities)

    child_expansion_params = [
        parent_entity_property,
        parent_entity_dcid,
        child_entity_type,
    ]
    if any(child_expansion_params):
        if not all(child_expansion_params):
            raise ValueError(
                "To use child entity expansion, all of 'parent_entity_property', "
                "'parent_entity_dcid', and 'child_entity_type' must be provided."
            )
        if parent_entity_property in entities_payload:
            raise ValueError(
                f"Property '{parent_entity_property}' cannot be specified in both 'entities' "
                "and child expansion parameters."
            )
        entities_payload[parent_entity_property] = {  # type: ignore[index]
            "parent_dcid": parent_entity_dcid,
            "child_type": child_entity_type,
        }

    payload = {
        "variable_dcid": variable_dcid,
        "entities": entities_payload,
        "source_override": source_override,
        "date": date,
        "date_range_start": date_range_start,
        "date_range_end": date_range_end,
    }
    return await client.post("agent/get_observations", payload)


async def search_indicators(
    query: str,
    places: list[str] | None = None,
    parent_place: str | None = None,
    per_search_limit: int = 10,
    *,
    include_topics: bool = True,
) -> dict[str, Any]:
    """Searches for indicators via the Agent API agent/search_indicators endpoint."""
    client = _get_client()
    payload = {
        "query": query,
        "places": places or [],
        "parent_place": parent_place,
        "per_search_limit": per_search_limit,
        "include_topics": include_topics,
        "target": client.search_scope,
    }

    return await client.post("agent/search_indicators", payload)


async def get_variable_metadata(
    variable_dcids: list[str],
    entity_dcids: list[str],
) -> dict[str, Any]:
    """Retrieves rich structural metadata (definitions, coverage, and provenances) for variables."""
    client = _get_client()
    payload = {
        "variable_dcids": variable_dcids,
        "entity_dcids": entity_dcids,
    }
    return await client.post("agent/get_variable_metadata", payload)
