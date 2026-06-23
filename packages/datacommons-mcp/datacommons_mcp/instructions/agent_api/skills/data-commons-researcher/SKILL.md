---
name: data-commons-researcher
description: Guidelines, heuristics, and workflows for concept splitting, place resolution, variable metadata assessment, child-level sampling, and retrieving statistical observations from Data Commons.
---

## Foundational Knowledge: Data Commons Graph Structure

Data Commons organizes data into two main structural hierarchies. Understanding these is key to choosing your place names and variables:

1. **Topics (Variable Hierarchy)**: A taxonomy of categories (e.g., `Health` -> `Clinical Data` -> `Medical Conditions`). Topics contain sub-topics and individual variables.
2. **Places (Geographic Hierarchy)**: A taxonomy of spatial containment (e.g., `World` -> `Continent` -> `Country` -> `State` -> `County`).

### Data Availability & Efficiency Tips:

* **Direct Containment Efficiency**: Querying the direct child places of a parent (e.g., all counties inside California) is highly optimized and returns faster than querying arbitrary cross-border place sets.

---

## 1. The Three-Step Tool Pipeline

When researching statistics, always separate your work into three distinct phases to avoid context bloat:

1. **Discovery (`search_indicators` or `search_child_indicators`)**: Use this to find candidate variables matching the user's concept.
2. **Assessment (`get_variable_metadata`)**: Pass candidate variables and target locations to retrieve structural metadata, ensuring the dataset matches the required temporal range, granularity, and source trust.
3. **Retrieval (`get_observations` or `get_child_observations`)**: Fetch the actual timeseries arrays once the variables and facets have been qualified.

### CRITICAL: Always validate variable-place combinations first
* You **MUST** call discovery tools first to verify that the variable exists for the specified place.
* You **MUST** call `get_variable_metadata` to verify dataset facets (source, dates, coverage) before retrieving heavy observation arrays.
* Only use DCIDs returned by the discovery tools - never guess or assume variable-place combinations.

---

## 2. Discovery Heuristics: Concept Splitting & Parameter Tuning

To ensure focused and accurate candidate retrieval when calling discovery tools:

### A. Concept Extraction & Multi-Query Splitting

* **Search Single Concepts**: Always search for one semantic concept at a time.
* **Split Compound Queries**:
  * *Incorrect*: `query="health and unemployment rate"` (Causes search index confusion).
  * *Correct*: Split into two separate, sequential tool calls:
    1. `search_indicators(query="health", ...)`
    2. `search_indicators(query="unemployment rate", ...)`

### B. Parameter Configuration Guidelines

* **Toggling Topics (`include_topics`)**:
  * Set `include_topics=true` (Default) when the user's request is exploratory (e.g., *"What health data do you have?"*). Use the returned topics to map the category hierarchy.
  * Set `include_topics=false` when targeting a specific dataset or observation (e.g., *"Find the diabetes rate for California"*). This reduces the return payload size.
  * **Primary Rule**: If a user explicitly states what they want, follow their request. Otherwise, default to the guidelines above.

* **Setting Result Limits (`per_search_limit`)**:
  * Always stick to the default value of `10` to keep payloads small.
  * Do **not** increase the limit unless the user explicitly requests more candidate indicators.

---

## 3. Geographic Place Qualification & Fallback Recovery

Data Commons requires qualified geographic names to avoid database name conflicts.

### A. Core Qualification Rules

* **Never use DCIDs in Search Parameters**: Only pass qualified, human-readable English place names to `places` or `parent_place` in discovery tools (e.g., use `"California"`, not `"geoId/06"`).
* **Always Qualify Naming Ambiguities**: Add parent geographic or administrative context:
  * *New York*: Differentiate between `"New York City, USA"` and `"New York State, USA"`.
  * *Washington*: Differentiate between `"Washington, DC, USA"` and `"Washington State, USA"`.
  * *Madrid*: Differentiate between `"Madrid, Spain"` (city) and `"Community of Madrid, Spain"` (autonomous community).
  * *London*: Differentiate between `"London, UK"` and `"London, Ontario, Canada"`.
  * *Scotland*: Differentiate between `"Scotland, UK"` and `"Scotland County, USA"`.
* **Extracting names from other tools**: If you get place info from another tool, extract and use *only* the readable name, but always qualify it with geographic context.
* **Child Place Indicator Discovery Rule**: When searching for indicators related to child places within a parent (e.g., states within a country), you MUST use `search_child_indicators`, passing the parent place name in `parent_place` and a diverse sample of 5-6 of its child places in the `sample_child_places` list.

### B. Vague & Unqualified Query Fallbacks

* If a user asks a general question about available data without specifying a place (e.g., *"What data do you have?"*), proactively run a global topic lookup:
  * Call: `search_indicators(query="", places=["World"], include_topics=true)`.
  * Present the high-level World topics, then ask the user which specific place or territory they are interested in.
  * *Example response pattern*: "Here is a general overview of the data topics available for the World. You can also ask for this information for a specific place, like 'Africa', 'India', 'California, USA', or 'Paris, France'."

### C. Geographic Resolution Recovery (Troubleshooting)

* If the search tool resolves the wrong place (e.g., the user asked about Scotland but the results attach to "Scotland County, NC"):
  * Re-run `search_indicators` with explicit parent parameters (e.g., set `places=["Scotland, UK"]`).

---

## 4. Playbook Recipes & Call Examples

### Recipe 1: Data for a Specific Place
* **Goal**: Find and retrieve an indicator *about* a single place (e.g., "population of France").
* **Step 1 (Discovery)**: `search_indicators(query="population", places=["France"])`
* **Step 2 (Assessment)**: `get_variable_metadata(variable_dcids=["Count_Person"], entity_dcids=["country/FRA"])`
* **Step 3 (Retrieval)**: `get_observations(variable_dcid="Count_Person", place_dcid="country/FRA")`

### Recipe 2: Sampling Child Places & Containment Data
* **Goal**: Check and retrieve data across child places of a parent (e.g., "unemployment rate in Indian states" or "GDP of all countries in the World").
* **Step 1 (Discovery & Sampling)**: Call `search_child_indicators` using a diverse sample of child places to verify variable availability:
  * *Example (States in India)*: `search_child_indicators(query="unemployment", parent_place="India", sample_child_places=["Uttar Pradesh, India", "Maharashtra, India", "Tripura, India", "Bihar, India", "Kerala, India"])`
  * *Example (Countries in the World)*: `search_child_indicators(query="GDP", parent_place="World", sample_child_places=["USA", "China", "Germany", "Nigeria", "Brazil"])`
* **Proxy Logic rules**:
  1. If a sampled child place shows data in `placesWithData` for a variable, assume that variable is available across all child places of that type.
  2. If no sampled child place shows data, assume the variable is not available at the child level.
  3. **Definitiveness of Child Search**: The results of `search_child_indicators` are absolute and definitive for the targeted child places. If a variable or concept does not appear in the child search results, it is guaranteed not to exist for those child places. Do NOT run follow-up global searches (`search_indicators`) to double-check or verify if the variable exists elsewhere.
  4. **No Redundant Single-Place Pings**: If a variable is confirmed via `search_child_indicators` or has child place coverage, proceed directly to `get_child_observations` (using `latest` or a narrow range). Do NOT run redundant single-place `get_observations` calls to verify the variable's active status.
  5. Determine the common child place type (e.g. `"State"` or `"Country"`) from the returned `dcidPlaceTypeMappings`.
* **Step 2 (Assessment)**: Verify facets and date ranges for the variable across the child level by passing the resolved DCIDs of the sampled child places:
  * `get_variable_metadata(variable_dcids=["unemployment_rate_dcid"], entity_dcids=["resolved_child_dcid_1", "resolved_child_dcid_2", "..."])`
* **Step 3 (Retrieval)**: Query observations for **ALL** child places of the determined type:
  * `get_child_observations(variable_dcid="unemployment_rate_dcid", parent_place_dcid="country/IND", child_place_type="State")`

---

## 5. Child Place Type Determination Heuristics

Before calling `get_child_observations`, inspect the `dcidPlaceTypeMappings` returned by `search_child_indicators` to determine the value for the `child_place_type` parameter:
1. **Common Type**: Find the place type common to ALL sampled child places.
2. **Specific Type Priority**: If multiple types are common to all child places, choose the most specific type (e.g., prefer `"County"` over `"AdministrativeArea2"`).
3. **Majority Fallback**: If no single type is common to all, use the type that maps to a clear majority (50%+ threshold) of the sample.
4. **Resolution Failure**: If there is no common type and no majority type, child-place mode is not supported. Fall back to making individual `get_observations` calls for each child place.

---

## 6. Bounded Date Query & Date Filtering Rules

To prevent payload saturation and context window exhaustion when fetching time-series observations:

### A. Child Places Mode Constraint
* When calling `get_child_observations`, **never** set `date="all"`.
* **Safe Date Strategies**:
  * Set `date="latest"` to retrieve only the most recent data point for each child place.
  * Explicitly define a narrow window using `date_range_start` and `date_range_end` (e.g., `2020` to `2023`).

### B. Date Range Boundary Interpretations
When `date="range"` is used, the date ranges are evaluated as follows:
* **Start Date Only**: If only `date_range_start` is specified, the response will contain all observations starting at and after that date (inclusive).
* **End Date Only**: If only `date_range_end` is specified, the response will contain all observations before and up to that date (inclusive).
* **Both Boundaries**: If both are specified, the response contains observations within the provided range (inclusive).
* **Default Fallback**: If you do not provide any date parameters, the tool will automatically fetch only the `'latest'` observation.
