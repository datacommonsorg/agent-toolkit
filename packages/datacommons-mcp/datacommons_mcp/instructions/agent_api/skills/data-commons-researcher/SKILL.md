---
name: data-commons-researcher
description: Guidelines, heuristics, and workflows for concept splitting, parameter tuning, place resolution, variable metadata assessment, and retrieving statistical observations from Data Commons for specific places.
---

## Foundational Knowledge: Data Commons Graph Structure

Data Commons organizes data into two main structural hierarchies. Understanding these is key to choosing your place names and variables:

1. **Topics (Variable Hierarchy)**: A taxonomy of categories (e.g., `Health` -> `Clinical Data` -> `Medical Conditions`). Topics contain sub-topics and individual variables.
2. **Places (Geographic Hierarchy)**: A taxonomy of spatial containment (e.g., `World` -> `Continent` -> `Country` -> `State` -> `County`).

### Data Availability & Efficiency Tips:

* **Country-Level Priority**: Data coverage is always highest and most complete at the `Country` level. If a variable is missing at sub-national levels, fall back to checking country-level scope.
* **Child Places Routing**: If the user's query asks for statistics across child places or within a geographic containment hierarchy (e.g., *"unemployment rate in all counties of California"* or *"GDP of countries in Africa"*), you MUST read the specialized skill resource at 'skill://data-commons-child-places-researcher/SKILL.md' instead.

---

## 1. The Three-Step Tool Pipeline

When researching statistics for specific places, always separate your work into three distinct phases to avoid context bloat:

1. **Discovery (`search_indicators`)**: Use this to find candidate variables matching the user's concept.
2. **Assessment (`get_variable_metadata`)**: Pass candidate variables and target locations to retrieve structural metadata, ensuring the dataset matches the required temporal range, granularity, and source trust.
3. **Retrieval (`get_observations`)**: Fetch the actual timeseries arrays once the variables and facets have been qualified.

### CRITICAL: Always validate variable-place combinations first
* You **MUST** call `search_indicators` first to verify that the variable exists for the specified place.
* You **MUST** call `get_variable_metadata` to verify dataset facets (source, dates, coverage) before retrieving heavy observation arrays.
* Only use DCIDs returned by `search_indicators` - never guess or assume variable-place combinations.
* This ensures data availability and prevents errors from invalid combinations.

### Multi-Entity Discovery Routing Hook
After calling `search_indicators` or `get_variable_metadata`, inspect the `observation_properties` list on candidate variables:
* If `observation_properties` contains multiple entity properties (e.g. `["donor", "recipient"]` or `["exportingEntity", "importingEntity"]`), this indicator is a **Multi-Entity Statistical Variable**. You MUST switch to reading `skill://data-commons-multi-entity-researcher/SKILL.md` and call `get_multi_entity_observations`.

---

## 2. Discovery Heuristics: Concept Splitting & Parameter Tuning

To ensure focused and accurate candidate retrieval when calling `search_indicators`:

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

* **Never use DCIDs in Search Parameters**: Only pass qualified, human-readable English place names to `places` in `search_indicators` (e.g., use `"California"`, not `"geoId/06"`).
* **Always Qualify Naming Ambiguities**: Add parent geographic or administrative context:
  * *New York*: Differentiate between `"New York City, USA"` and `"New York State, USA"`.
  * *Washington*: Differentiate between `"Washington, DC, USA"` and `"Washington State, USA"`.
  * *Madrid*: Differentiate between `"Madrid, Spain"` (city) and `"Community of Madrid, Spain"` (autonomous community).
  * *London*: Differentiate between `"London, UK"` and `"London, Ontario, Canada"`.
  * *Scotland*: Differentiate between `"Scotland, UK"` and `"Scotland County, USA"`.
* **Extracting names from other tools**: If you get place info from another tool, extract and use *only* the readable name, but always qualify it with geographic context.

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

### Recipe 2: No Place Filtering
* **Goal**: Find indicators for a query without checking any specific place (e.g., "what trade data do you have").
* **Call**: `search_indicators(query="trade")`. Do not set `places`.

---

## 5. Processing `search_indicators` Responses

Always treat results as **candidates**. You must filter, rank, and verify them based on the user's full context.

### A. Response Structure Reference
```json
{
  "topics": [
    {
      "dcid": "dc/t/TopicDcid",
      "memberTopics": ["dc/t/SubTopic1", "..."],
      "memberVariables": ["dc/v/Variable1", "..."],
      "placesWithData": ["country/FRA", "..."]
    }
  ],
  "variables": [
    {
      "dcid": "dc/v/VariableDcid",
      "placesWithData": ["country/FRA", "country/CAN", "..."]
    }
  ],
  "dcidNameMappings": {
    "dc/t/TopicDcid": "Readable Topic Name",
    "dc/v/VariableDcid": "Readable Variable Name",
    "country/FRA": "France",
    "country/CAN": "Canada"
  },
  "status": "SUCCESS"
}
```

### B. Field Mapping Rules
* **`topics`**: (Only if `include_topics=true`) Use `dcidNameMappings` to resolve readable names for presentation to the user.
* **`variables`**: Individual data indicators. Use `dcidNameMappings` to resolve readable names.
* **`placesWithData`**: (Only if `places` was in the request) Represents which of the requested places have data for that specific indicator.
* **`dcidNameMappings`**: Use this to map all returned DCIDs (topics, variables, and places) to human-readable names.

---

## 6. Processing `get_variable_metadata` Responses

Use this response to verify dataset coverage, date ranges, and sources before fetching observations.

### A. Response Structure Reference
```json
{
  "status": "SUCCESS",
  "variables": {
    "Count_Person": {
      "id": "Count_Person",
      "name": "Total population",
      "description": "The total number of people in a population.",
      "facets": [
        {
          "id": "2911625765",
          "provenanceId": "dc/base/France_Demographics",
          "obsCount": 35,
          "dateRange": { "start": "1991", "end": "2025" },
          "scope": { "entityCoverage": ["country/FRA"] }
        }
      ]
    }
  },
  "provenances": {
    "dc/base/France_Demographics": {
      "id": "dc/base/France_Demographics",
      "properties": {
        "source": "National Institute of Statistics and Economic Studies, France",
        "url": "https://www.insee.fr/en/statistiques/8333211"
      }
    }
  }
}
```

### B. Field Mapping Rules
* **`variables`**: Contains metadata per variable DCID. Inspect `facets` to confirm if `dateRange` matches the user's temporal request.
* **`provenances`**: Maps provenance IDs to authoritative source details (`source`, `url`). Use this for mandatory data attribution.

---

## 7. Bounded Date Query & Date Filtering Rules

To prevent payload saturation and context window exhaustion when fetching time-series observations:

### A. Date Range Boundary Interpretations
When `date="range"` is used in `get_observations`, the date ranges are evaluated as follows:
* **Start Date Only**: If only `date_range_start` is specified, the response will contain all observations starting at and after that date (inclusive).
* **End Date Only**: If only `date_range_end` is specified, the response will contain all observations before and up to that date (inclusive).
* **Both Boundaries**: If both are specified, the response contains observations within the provided range (inclusive).
* **Default Fallback**: If you do not provide any date parameters (`date`, `date_range_start`, or `date_range_end`), the tool will automatically fetch only the `'latest'` observation.

---

## 8. Processing `get_observations` Responses

### A. Response Structure Reference
```json
{
  "variable": { "dcid": "Count_Person", "name": "Total population" },
  "placeObservations": [
    {
      "place": { "dcid": "country/FRA", "name": "France", "typeOf": ["Country"] },
      "timeSeries": [{ "date": "2025", "value": 68605616 }]
    }
  ],
  "sourceMetadata": { "sourceId": "2911625765", "provenanceUrl": "https://www.insee.fr" },
  "alternativeSources": []
}
```

### B. Field Mapping Rules
* **`variable`**: Details about the statistical variable requested.
* **`placeObservations`**: A list of observations, one entry per place. Each entry contains:
  * `place`: Details about the observed place (DCID, name, type).
  * `timeSeries`: A list of `(date, value)` objects.
* **`sourceMetadata`**: Primary authoritative data source information.
* **`alternativeSources`**: Secondary available sources for validation or cross-referencing.
