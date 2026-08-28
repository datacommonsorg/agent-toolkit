---
name: data-commons-child-places-researcher
description: Guidelines, heuristics, and workflows for concept splitting, parent/child place resolution, sub-national sampling, place type determination, and retrieving statistical observations for child places from Data Commons.
---

## Foundational Knowledge: Data Commons Graph Structure

Data Commons organizes data into two main structural hierarchies. Understanding these is key to choosing your place names and variables:

1. **Topics (Variable Hierarchy)**: A taxonomy of categories (e.g., `Health` -> `Clinical Data` -> `Medical Conditions`). Topics contain sub-topics and individual variables.
2. **Places (Geographic Hierarchy)**: A taxonomy of spatial containment (e.g., `World` -> `Continent` -> `Country` -> `State` -> `County`).

### Data Availability & Efficiency Tips:

* **Direct Containment Efficiency**: Querying the direct child places of a parent (e.g., all counties inside California) is highly optimized and returns faster than querying arbitrary cross-border place sets.
* **Single-Place Routing**: If the user's query asks for statistics about a single specific place (e.g., *"population of France"* or *"GDP of California"*), you MUST read the base skill resource at 'skill://data-commons-researcher/SKILL.md' instead.

---

## 1. The Three-Step Tool Pipeline

When researching statistics across child places within a parent entity, always separate your work into three distinct phases to avoid context bloat:

1. **Discovery (`search_child_indicators`)**: Use this to find candidate variables matching the user's concept that are available at the sub-national/child level.
2. **Assessment (`get_variable_metadata`)**: Pass candidate variables and target child locations to retrieve structural metadata, ensuring the dataset matches the required temporal range, granularity, and source trust.
3. **Retrieval (`get_child_observations`)**: Fetch the actual timeseries arrays across all child places of a specified type once the variables and facets have been qualified.

### CRITICAL: Always validate variable-place combinations first
* You **MUST** call `search_child_indicators` first to verify that the variable exists for the specified child places.
* You **MUST** call `get_variable_metadata` to verify dataset facets (source, dates, coverage) for sampled child places before retrieving heavy observation arrays.
* Only use DCIDs returned by `search_child_indicators` - never guess or assume variable-place combinations.
* This ensures data availability and prevents errors from invalid combinations.

### Multi-Entity Discovery Routing Hook
After calling `search_child_indicators` or `get_variable_metadata`, inspect the `observation_properties` list on candidate variables:
* If `observation_properties` contains multiple entity properties (e.g. `["donor", "recipient"]` or `["exportingEntity", "importingEntity"]`), this indicator is a **Multi-Entity Statistical Variable**. You MUST switch to reading `skill://data-commons-multi-entity-researcher/SKILL.md` and call `get_multi_entity_observations`.

---

## 2. Discovery Heuristics: Concept Splitting & Parameter Tuning

To ensure focused and accurate candidate retrieval when calling `search_child_indicators`:

### A. Concept Extraction & Multi-Query Splitting

* **Search Single Concepts**: Always search for one semantic concept at a time.
* **Split Compound Queries**:
  * *Incorrect*: `query="health and unemployment rate"` (Causes search index confusion).
  * *Correct*: Split into two separate, sequential tool calls:
    1. `search_child_indicators(query="health", ...)`
    2. `search_child_indicators(query="unemployment rate", ...)`

### B. Parameter Configuration Guidelines

* **Toggling Topics (`include_topics`)**:
  * Set `include_topics=true` (Default) when the user's request is exploratory (e.g., *"What health data do you have for California counties?"*).
  * Set `include_topics=false` when targeting a specific dataset or observation (e.g., *"Find the diabetes rate for California counties"*). This reduces the return payload size.

* **Setting Result Limits (`per_search_limit`)**:
  * Always stick to the default value of `10` to keep payloads small.
  * Do **not** increase the limit unless the user explicitly requests more candidate indicators.

---

## 3. Geographic Place Qualification & Fallback Recovery

Data Commons requires qualified geographic names to avoid database name conflicts.

### A. Core Qualification Rules

* **Never use DCIDs in Search Parameters**: Only pass qualified, human-readable English place names to `parent_place` or `sample_child_places` in `search_child_indicators` (e.g., use `"California"`, not `"geoId/06"`).
* **Always Qualify Naming Ambiguities**: Add parent geographic or administrative context when specifying parent or sample child places:
  * *New York*: Differentiate between `"New York City, USA"` and `"New York State, USA"`.
  * *Washington*: Differentiate between `"Washington, DC, USA"` and `"Washington State, USA"`.
  * *Madrid*: Differentiate between `"Madrid, Spain"` (city) and `"Community of Madrid, Spain"` (autonomous community).
  * *London*: Differentiate between `"London, UK"` and `"London, Ontario, Canada"`.
  * *Scotland*: Differentiate between `"Scotland, UK"` and `"Scotland County, USA"`.
* **Extracting names from other tools**: If you get place info from another tool, extract and use *only* the readable name, but always qualify it with geographic context.

### B. Child Place Indicator Discovery Rule
* When searching for indicators related to child places within a parent (e.g., states within a country, or counties within a state), you MUST call `search_child_indicators`, passing the parent entity in the `parent_place` parameter and a diverse sample of 5-6 of its child places in the `sample_child_places` list. This ensures the discovery of indicators that have data at the child place level.

### C. Vague & Unqualified Query Fallbacks
* If a user asks a general or vague question about available sub-national data without specifying target indicators (e.g., *"What child data do you have for California?"* or *"What statistics exist for US counties?"*), proactively run a child topic lookup:
  * Call: `search_child_indicators(query="", parent_place="California", sample_child_places=["Los Angeles County, CA", "San Francisco County, CA", "Alpine County, CA"], include_topics=true)`.
  * Present the returned high-level topics for that place's children to guide the user's focus.

### D. Geographic Resolution Recovery (Troubleshooting)

* If the search tool resolves the wrong parent place:
  * Re-run `search_child_indicators` with explicit administrative parameters.

---

## 4. Playbook Recipes & Call Examples

### Recipe: Sampling Child Places & Containment Data
* **Goal**: Check and retrieve data across child places of a parent (e.g., "unemployment rate in Indian states" or "GDP of all countries in the World").
* **Step 1 (Discovery & Sampling)**: Call `search_child_indicators` using a diverse sample of child places to verify variable availability:
  * *Example (States in India)*: `search_child_indicators(query="unemployment", parent_place="India", sample_child_places=["Uttar Pradesh, India", "Maharashtra, India", "Tripura, India", "Bihar, India", "Kerala, India"])`
  * *Example (Countries in the World)*: `search_child_indicators(query="GDP", parent_place="World", sample_child_places=["USA", "China", "Germany", "Nigeria", "Brazil"])`
  * *Example (Administrative Level Sampling for Cities)*: `search_child_indicators(query="population", parent_place="USA", sample_child_places=["New York City, USA", "Los Angeles, USA", "Chicago, USA", "Houston, USA", "Phoenix, USA"])`
  * *Example (Administrative Level Sampling for States)*: `search_child_indicators(query="population", parent_place="USA", sample_child_places=["California, USA", "Texas, USA", "Florida, USA", "New York State, USA", "Pennsylvania, USA"])`
* **Proxy Logic rules**:
  1. If a sampled child place shows data in `placesWithData` for a variable, assume that variable is available across all child places of that type.
  2. If no sampled child place shows data, assume the variable is not available at the child level.
  3. **Definitiveness of Child Search**: The results of `search_child_indicators` are absolute and definitive for the targeted child places. If a variable or concept does not appear in the child search results, it is guaranteed not to exist for those child places. Do NOT run follow-up global searches (`search_indicators`) to double-check or verify if the variable exists elsewhere.
  4. **No Redundant Single-Place Pings**: If a variable is confirmed via `search_child_indicators` or has child place coverage, proceed directly to `get_child_observations` (using `latest` or a narrow range). Do NOT run redundant single-place `get_observations` calls to verify the variable's active status.
  5. Determine the common child place type (e.g. `"State"` or `"Country"`) from the returned `dcidPlaceTypeMappings`.
* **Step 2 (Assessment)**: Verify facets and date ranges for the variable across the child level by passing the resolved DCIDs of the sampled child places:
  * `get_variable_metadata(variable_dcids=["unemployment_rate_dcid"], entity_dcids=["resolved_child_dcid_1", "resolved_child_dcid_2", "..."])`
* **Step 3 (Retrieval)**: Query observations for **ALL** child places of the determined type using `get_child_observations`:
  * `get_child_observations(variable_dcid="unemployment_rate_dcid", parent_place_dcid="country/IND", child_place_type="State")`

---

## 5. Processing `search_child_indicators` Responses

Always treat results as **candidates**. You must filter, rank, and verify them based on the user's full context.

### A. Response Structure Reference
```json
{
  "topics": [
    {
      "dcid": "dc/t/TopicDcid",
      "memberTopics": ["dc/t/SubTopic1", "..."],
      "memberVariables": ["dc/v/Variable1", "..."],
      "placesWithData": ["geoId/06037", "..."]
    }
  ],
  "variables": [
    {
      "dcid": "dc/v/VariableDcid",
      "placesWithData": ["geoId/06037", "geoId/06075", "..."]
    }
  ],
  "dcidNameMappings": {
    "dc/t/TopicDcid": "Readable Topic Name",
    "dc/v/VariableDcid": "Readable Variable Name",
    "geoId/06037": "Los Angeles County, CA",
    "geoId/06075": "San Francisco County, CA"
  },
  "dcidPlaceTypeMappings": {
    "geoId/06037": ["County"],
    "geoId/06075": ["County"]
  },
  "status": "SUCCESS"
}
```

### B. Field Mapping Rules
* **`topics`**: (Only if `include_topics=true`) Use `dcidNameMappings` to resolve readable names.
* **`variables`**: Individual data indicators. Use `dcidNameMappings` to resolve readable names.
* **`placesWithData`**: Represents which of the sampled child places have data for that specific indicator.
* **`dcidNameMappings`**: Use this to map returned DCIDs to human-readable names.
* **`dcidPlaceTypeMappings`**: Maps place DCIDs to their types. Use this to determine the `child_place_type` parameter when calling `get_child_observations`.

---

## 6. Processing `get_variable_metadata` Responses

Use this response to verify dataset coverage, date ranges, and sources for sampled child places before fetching full observation arrays.

### A. Response Structure Reference
```json
{
  "status": "SUCCESS",
  "variables": {
    "UnemploymentRate_Person": {
      "id": "UnemploymentRate_Person",
      "name": "Unemployment Rate",
      "facets": [
        {
          "id": "2176550201",
          "provenanceId": "dc/base/BLS_CP",
          "obsCount": 12,
          "dateRange": { "start": "2020", "end": "2024" },
          "scope": { "entityCoverage": ["geoId/06037"] }
        }
      ]
    }
  },
  "provenances": {
    "dc/base/BLS_CP": {
      "id": "dc/base/BLS_CP",
      "properties": {
        "source": "Bureau of Labor Statistics",
        "url": "https://www.bls.gov"
      }
    }
  }
}
```

### B. Field Mapping Rules
* **`variables`**: Contains metadata per variable DCID. Inspect `facets` to confirm temporal range (`dateRange`) and validity across the sampled child places.
* **`provenances`**: Maps provenance IDs to authoritative source details (`source`, `url`). Use this for mandatory data attribution.

---

## 7. Child Place Type Determination Heuristics

Before calling `get_child_observations`, inspect the `dcidPlaceTypeMappings` returned by `search_child_indicators` to determine the value for the `child_place_type` parameter:
1. **Common Type**: Find the place type common to ALL sampled child places.
2. **Specific Type Priority**: If multiple types are common to all child places, choose the most specific type (e.g., prefer `"County"` over `"AdministrativeArea2"`).
3. **Majority Fallback**: If no single type is common to all, use the type that maps to a clear majority (50%+ threshold) of the sample.
4. **Resolution Failure**: If there is no common type and no majority type, child-place mode is not supported. Fall back to making individual `get_observations` calls in single-place mode for each child place using the base skill resource at 'skill://data-commons-researcher/SKILL.md'.

---

## 8. Bounded Date Query & Date Filtering Rules

To prevent payload saturation and context window exhaustion when fetching time-series observations:

### A. Child Places Mode Constraint
* When calling `get_child_observations` with `child_place_type` active, **never** set `date="all"`.
* **Safe Date Strategies**:
  * Set `date="latest"` to retrieve only the most recent data point for each child place.
  * Explicitly define a narrow window using `date_range_start` and `date_range_end` (e.g., `2020` to `2023`).

### B. Date Range Boundary Interpretations
When `date="range"` is used, the date ranges are evaluated as follows:
* **Start Date Only**: If only `date_range_start` is specified, the response will contain all observations starting at and after that date (inclusive).
* **End Date Only**: If only `date_range_end` is specified, the response will contain all observations before and up to that date (inclusive).
* **Both Boundaries**: If both are specified, the response contains observations within the provided range (inclusive).
* **Default Fallback**: If you do not provide any date parameters (`date`, `date_range_start`, or `date_range_end`), the tool will automatically fetch only the `'latest'` observation.

---

## 9. Processing `get_child_observations` Responses

All child observation responses return a uniform dual-table structure:
1. **`entityMetadata`**: Maps child entity DCIDs to human-readable names and types using tabular `columns` and `rows`.
2. **`data` Table**: Matrix of observations containing columns `["observationAbout", "date", "value"]` and tabular `rows`.

### A. Response Structure Reference
```json
{
  "variable": {
    "dcid": "UnemploymentRate_Person",
    "name": "Unemployment Rate",
    "typeOf": ["StatisticalVariable"]
  },
  "sourceMetadata": {
    "sourceId": "2176550201",
    "observationPeriod": "P1Y",
    "provenanceUrl": "https://www.bls.gov",
    "unit": "Percent"
  },
  "alternativeSources": [],
  "entityMetadata": {
    "columns": ["dcid", "name", "typeOf"],
    "rows": [
      ["geoId/06037", "Los Angeles County", ["AdministrativeArea2", "County", "Place"]],
      ["geoId/06075", "San Francisco County", ["AdministrativeArea2", "County", "Place"]]
    ]
  },
  "data": {
    "columns": ["observationAbout", "date", "value"],
    "rows": [
      ["geoId/06037", "2024", 5.4],
      ["geoId/06075", "2024", 4.1]
    ]
  }
}
```

### B. Field Mapping Rules
* **`variable`**: Details about the statistical variable requested.
* **`entityMetadata`**: Matrix of child entity metadata:
  * `columns`: Array of column names (`dcid`, `name`, `typeOf`).
  * `rows`: Tabular arrays of `[child_dcid, entity_name, entity_types]`.
* **`data`**: Matrix of child observations:
  * `columns`: Array of column names (`observationAbout`, `date`, `value`).
  * `rows`: Tabular arrays of `[child_dcid, date, value]`.
* **`sourceMetadata`**: Primary authoritative data source information.
* **`alternativeSources`**: Secondary available sources.


