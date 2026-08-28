---
name: data-commons-multi-entity-researcher
description: Guidelines, heuristics, and workflows for discovering, assessing, and retrieving observations for multi-entity relationship statistical variables (e.g. foreign aid flows, bilateral trade, international migration) from Data Commons.
---

## Foundational Knowledge: Multi-Entity Graph Model

Data Commons models complex relationships between multiple entities using **Multi-Entity Statistical Variables**. Unlike standard single-entity variables that measure a property of one location (`observationAbout`), multi-entity variables track directed interactions, flows, or interactions between multiple entity roles (e.g., `donor` and `recipient`, `exportingEntity` and `importingEntity`, `origin` and `destination`).

---

## 1. The Three-Step Multi-Entity Tool Pipeline

When researching multi-entity relationship statistics, separate your work into three distinct phases:

1. **Discovery (`search_indicators`)**: Find candidate variables for your concept (e.g., query `"gross ODA aid"`). Inspect the returned `observation_properties` list on each variable candidate (e.g., `["donor", "recipient"]`).
2. **Assessment (`get_variable_metadata`)**: Pass candidate variables and entity DCIDs to verify dataset coverage, date ranges, provenances, and confirm the specific `observationProperties`.
3. **Retrieval (`get_multi_entity_observations`)**: Fetch the observation tables using the mapped entity properties.

---

## 2. Parameter Configuration & Entity Property Mapping

### A. Entity Mapping (`entities` dictionary - Required)
Map each entity property key (from `observation_properties`, e.g. `"donor"`, `"recipient"`) to its corresponding list of entity DCIDs:
* *Direct Bilateral Pair*:
  ```json
  "entities": {
    "donor": ["country/ARE"],
    "recipient": ["country/AFG"]
  }
  ```

### B. Child Entity Expansion
To fetch observations across child places for a target property (e.g. UAE aid to all recipient countries):
* Set fixed DCIDs in `entities` for known roles (e.g. `"donor": ["country/ARE"]`).
* Set flat child expansion fields for the target property:
  - `parent_entity_property`: `"recipient"`
  - `parent_entity_dcid`: `"Earth"`
  - `child_entity_type`: `"Country"`

---

## 3. Playbook Recipes & Call Examples

### Recipe 1: Direct Bilateral Pair (e.g., "Foreign aid from UAE to Afghanistan")
* **Step 1 (Discovery)**: `search_indicators(query="official development assistance")`
* **Step 2 (Assessment)**: `get_variable_metadata(variable_dcids=["Amount_EconomicActivity_GrossODA"], entity_dcids=["country/ARE", "country/AFG"])`
* **Step 3 (Retrieval)**: `get_multi_entity_observations(variable_dcid="Amount_EconomicActivity_GrossODA", entities={"donor": ["country/ARE"], "recipient": ["country/AFG"]})`

### Recipe 2: Multi-Entity Child Expansion (e.g., "Foreign aid from UAE to all countries")
* **Step 1 (Discovery)**: `search_indicators(query="official development assistance")`
* **Step 2 (Assessment)**: `get_variable_metadata(variable_dcids=["Amount_EconomicActivity_GrossODA"], entity_dcids=["country/ARE"])`
* **Step 3 (Retrieval)**: `get_multi_entity_observations(variable_dcid="Amount_EconomicActivity_GrossODA", entities={"donor": ["country/ARE"]}, parent_entity_property="recipient", parent_entity_dcid="Earth", child_entity_type="Country")`

---

## 4. Processing Multi-Entity Responses

All observation responses return a uniform dual-table structure:
1. **`entityMetadata`**: Maps entity DCIDs to human-readable names and types (e.g., `"country/ARE"` -> `"United Arab Emirates"`).
2. **`data` Table**: Matrix of observations containing columns for each entity property, `date`, and `value`.

Always join `entityMetadata` with the `data` table rows to present human-readable entity names and cite the authoritative data source provenance.
