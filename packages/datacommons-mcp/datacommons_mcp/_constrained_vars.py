from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from datacommons_client import DataCommonsClient


def _fetch_statvar_constraints(
    client: DataCommonsClient, place_like_constraints: list[str]
) -> dict:
    """Return {constraint_property: [statvar_dcid, ...]}.

    Args:
        client: DataCommonsClient.
        place_like_constraints: List of constraint property names
        (e.g., ["lendingEntity", "DevelopmentFinanceRecipient"]).

    Returns:
        Mapping of constraint property names to lists of statvar DCIDs.
    """
    if not place_like_constraints:
        return {}

    properties = client.node.fetch(
        node_dcids=place_like_constraints, expression="<-constraintProperties"
    ).get_properties()

    return {
        prop: [sv.dcid for sv in values.get("constraintProperties", [])]
        for prop, values in properties.items()
    }


def _extract_place_like(
    client: DataCommonsClient,
    nodes: list[str],
    constraint: str,
) -> dict[str, list[str]]:
    """Return {place_dcid: [statvar_dcid, ...]} for a single constraint."""
    if not nodes:
        return {}

    node_props = client.node.fetch_property_values(
        node_dcids=nodes, properties=[constraint]
    ).get_properties()

    result = {}

    for dcid, node in node_props.items():
        entity = node[constraint]
        if not entity:
            continue
        result.setdefault(entity[0].dcid, []).append(dcid)

    return result


def _merge_dicts(dicts: list[dict]) -> dict[str, set[str]]:
    """Merge list of dicts via set union of values."""
    merged: dict[str, set[str]] = defaultdict(set)
    for d in dicts:
        for k, vs in d.items():
            merged[k].update(vs)
    return merged


def place_statvar_constraint_mapping(
    client: DataCommonsClient,
    place_like_constraints: list[str],
    *,
    max_workers: int | None = None,
) -> dict[str, set[str]]:
    """Build {place_dcid: [statvar_dcid, ...]} across constraints concurrently.

      1) For each constraint, find statvars that reference it.
      2) Concurrently fetch per-constraint place-like values for those statvars.
      3) Merge per-constraint dicts via set-union.

    Args:
      client: DataCommonsClient.
      place_like_constraints: Constraint property names (e.g., ["lendingEntity", "DevelopmentFinanceRecipient"]).
      max_workers: Optional thread pool size. Defaults to min(2, number of constraints).

    Returns:
      Mapping of place-like DCIDs to lists of statvar DCIDs.

    TODO: https://github.com/datacommonsorg/agent-toolkit/issues/47 - Remove once the
      new endpoint is live.
    """
    constraint_to_svs = _fetch_statvar_constraints(client, place_like_constraints)
    if not constraint_to_svs:
        return {}

    workers = max_workers or min(2, len(constraint_to_svs))

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_extract_place_like, client, svs, constraint): constraint
            for constraint, svs in constraint_to_svs.items()
        }
        results = [fut.result() for fut in as_completed(futures)]

    # Merge per-constraint dicts via set union.
    return _merge_dicts(results)
