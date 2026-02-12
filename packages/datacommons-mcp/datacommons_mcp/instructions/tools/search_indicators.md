**Purpose:**
Search for topics and variables (collectively called "indicators") available in the Data Commons Knowledge Graph.

**Core Concept: Results are Candidates**
This tool returns *candidate* indicators that match your query. You must always filter and rank these results based on the user's context to find the most relevant one.

**Background: Data Commons Structure**
Data Commons organizes data in two main hierarchies:

1. **Topics:** A hierarchy of categories (e.g., `Health` -> `Clinical Data` -> `Medical Conditions`). Topics contain sub-topics and member variables.

2. **Places:** A hierarchy of geographic containment (e.g., `World` -> `Continent` -> `Country` -> `State`).

**CRITICAL DATA PRINCIPLE:**
The *same* statistical concept (e.g., "Population") might use *different* indicator DCIDs for different place types (e.g., one DCID for `Country` and another for `State`). This tool is essential for discovering *which* specific indicators are available for the `places` you are querying.

**Efficiency Tips:**

* Data coverage is generally high at the `Country` level.

* Fetching direct children of a place (e.g., states in a country) is efficient.

### Parameters

**1. `query` (str, required)**

  - The search query for indicators (topics or variables).

  - **Examples:** `"health grants"`, `"carbon emissions"`, `"unemployment rate"`

  - **CRITICAL RULES:**
    * Search for one concept at a time to get focused results.
      - Instead of: "health and unemployment rate" (single search)
      - Use: "health" and "unemployment rate" as separate searches

**2. `places` (list[str], optional)**

  - A list of English, human-readable place names to filter indicators by.
  - If provided, the tool will only return indicators that have data for at least one of the specified places.
  - When `parent_place` is used, this parameter should **only** contain a sample of child places.
  - When `parent_place` is **not** used, this can contain any place.

**3. `parent_place` (str, optional)**

  - An English, human-readable name for a parent place.
  - Use this **only** when searching for indicators about a *type* of child place (e.g., "states in India").
  - When using this parameter, you **must** also provide a sample of child places in the `places` parameter.

**Place Name Qualification (CRITICAL):**
The following rules apply to **both** the `places` and `parent_place` parameters.

  - **ALWAYS qualify place names** with geographic context to avoid ambiguity (e.g., `"California, USA"`, `"Paris, France"`, `"Springfield, IL"`).

  - **ALWAYS specify administrative level** when ambiguous:
    - For the city: `"Madrid, Spain"`
    - For the autonomous community: `"Community of Madrid, Spain"`
    - Similarly, differentiate between `"New York City, USA"` and `"New York State, USA"`.

  - **Common Ambiguous Cases:**
    - **New York:** `"New York City, USA"` vs `"New York State, USA"`
    - **Madrid:** `"Madrid, Spain"` (city) vs `"Community of Madrid, Spain"`
    - **London:** `"London, UK"` (city) vs `"London, Ontario, Canada"`
    - **Washington:** `"Washington, DC, USA"` vs `"Washington State, USA"`
    - **Springfield:** `"Springfield, IL, USA"` vs `"Springfield, MO, USA"` (add state)

  - **NEVER** use DCIDs (e.g., `"geoId/06"`, `"country/CAN"`).
  - If you get place info from another tool, extract and use *only* the readable name, but always qualify it with geographic context.
  - When searching for indicators related to child places within a larger geographic entity (e.g., states within a country, or countries within a continent/the world), you MUST include the parent entity in the `parent_place` parameter and a diverse sample of 5-6 of its child places in the `places` list.
  - This ensures the discovery of indicators that have data at the child place level. Refer to 'Recipe 4: Sampling Child Places' for detailed examples.

**How to Use Place Parameters (Recipes):**

  - **Recipe 1: Data for a Specific Place**

    - **Goal:** Find an indicator *about* a single place (e.g., "population of France").

    - **Call:** `query="population"`, `places=["France"]`, `maybe_bilateral=False`

  - **Recipe 2: Sampling Child Places**

    - **Goal:** Check data availability for a *type* of child place (e.g., "population of Indian states" or "highest GDP countries" or "top 5 US states with lowest unemployment rate").

    - **Action:** You must *proxy* this request by sampling a few children.

    - **Example 1: Child places of a country**
      - **Call:**
        * `query="population"`
        * `parent_place="India"`
        * `places=["Uttar Pradesh, India", "Maharashtra, India", "Tripura, India", "Bihar, India", "Kerala, India"]`
      - **Logic:**
        1. Include the parent place ("India"). The tool uses this for context and to return its DCID.
        2. Include 5-6 *diverse* child places (e.g., try to pick large/small, north/south/east/west, if known).
        3. The results for these 5-6 places are a *proxy* for all children.
        4. If a sampled child place shows data for an indicator, assume that data is available for all child places of that type for that indicator.
            Conversely, if, after sampling, no child place shows data for a specific indicator, assume that data is not available for any of the child places
            for that indicator.

    - **Example 2: Child places of the World (Countries)**
      - **Call:**
        * `query="GDP"`
        * `parent_place="World"`
        * `places=["USA", "China", "Germany", "Nigeria", "Brazil"]`
      - **Logic:**
        1. Include the parent place ("World").
        2. Include 5-6 *diverse* child countries (e.g., from different continents, different economies).
        3. This sampling helps discover the correct indicator DCID used for the `Country` place type, which you can then use in other tools (like `get_observations` with the parent's DCID in the `place_dcid` parameter and `child_place_type='Country'`).

    - **Example 3: Administrative Level Sampling**

      - **Goal:** Check data availability for different administrative levels (e.g., "population of US cities" vs "population of US states").

      - **Call:**
        * **For Cities:** `query="population"`, `parent_place="USA"`, `places=["New York City, USA", "Los Angeles, USA", "Chicago, USA", "Houston, USA", "Phoenix, USA"]`
        * **For States:** `query="population"`, `parent_place="USA"`, `places=["California, USA", "Texas, USA", "Florida, USA", "New York State, USA", "Pennsylvania, USA"]`
      - **Logic:** Specify the exact administrative level you want to sample to avoid confusion between city and state data.

  - **Recipe 3: Potentially Bilateral Data**

    - **Goal:** Find an indicator that *might* be bilateral (e.g., "trade exports to France"). The data might be *about* France, or it might be *from* other places *to* France.

    - **Call:** `query="trade exports"`, `places=["France"]`, `maybe_bilateral=True`

  - **Recipe 4: Known Bilateral Data (Multi-Place)**

    - **Goal:** Find data *between* places (e.g., "trade from USA and Germany to France").

    - **Call:** `query="trade exports"`, `places=["USA", "Germany", "France"]`, `maybe_bilateral=True`

    - **Note:** The response's `places_with_data` will show which of "USA", "Germany", or "France" the observations are attached to. The other places are often part of the variable name itself.

  - **Recipe 5: No Place Filtering**

    - **Goal:** Find indicators for a query without checking any specific place (e.g., "what trade data do you have").

    - **Call:** `query="trade"`. Do not set `places` or `parent_place`.

    - **Result:** The tool returns matching indicators, but `places_with_data` will be empty.

**4. `per_search_limit` (int, optional, default=10, max=100)**

  - Maximum results per search.

  - **CRITICAL RULE:** Only set per_search_limit when explicitly requested by the user.
    - Use the default value (10) unless the user specifies a different limit
    - Don't assume the user wants more or fewer results

**5. `include_topics` (bool, optional, default=True)**

  - **Primary Rule:** If a user explicitly states what they want, follow their request. Otherwise, use these guidelines:

  - **`include_topics = True` (Default): For Exploration & Discovery**

    - **Purpose:** To explore the data hierarchy and find related variables.

    - **Use when:**

      - The user is exploring (e.g., "what basic health data do you have?").

      - You need to understand how data is organized to ask a better follow-up.

   - **Returns:** Both topics (categories) and variables.

  - **`include_topics = False`: For Specific Data**

    - **Purpose:** To find a specific variable for fetching data.

    - **Use when:**

      - The user's goal is to get a specific number or dataset (e.g., "find unemployment rate for United States").

    - **Returns:** Variables only.

**6. `maybe_bilateral` (bool, optional, default=False)**

  - Set to `True` if the query implies a relationship *between* places (e.g., "trade", "migration", "exports to France").

  - Set to `False` (default) for queries about a *property of* a place (e.g., "population", "unemployment rate", "carbon emissions in NYC").

  - See the "Recipes" in the `places` parameter section for specific examples.

### Special Query Scenarios

**Scenario 1: Vague, Unqualified Queries ("what data do you have?")**
  - **Action:** If a user asks a general question about available data, proactively call the tool for "World" to provide an initial overview.

  - **Call:** `query=""`, `places=["World"]`, `include_topics=True`

  - **Result:** This returns the top-level topics for the World.

  - **Agent Follow-up:** After showing the World data, consider asking if the user would like to see data for a different, more specific place if it seems helpful for the conversation.

  - **Example agent response:** "Here is a general overview of the data topics available for the World. You can also ask for this information for a specific place, like 'Africa', 'India', 'California, USA', or 'Paris, France'."

**Scenario 2: Ambiguous Place Names**

  - **Problem 1:** Geographic ambiguity - User asks for "Scotland", tool returns "Scotland County, USA".
  - **Solution:** Re-run with qualified name: `places=["Scotland, UK"]`

  - **Problem 2:** Administrative level ambiguity - User asks for "New York", tool returns state-level data when city-level was intended.
  - **Solution:** Specify administrative level: `places=["New York City, USA"]` vs `places=["New York State, USA"]`

### Response Structure

Returns a dictionary containing candidate indicators.

```json
{
  "topics": [
    {
      "dcid": "dc/t/TopicDcid",
      "member_topics": ["dc/t/SubTopic1", "..."],
      "member_variables": ["dc/v/Variable1", "..."],
      "places_with_data": ["geoId/06", "..."]
    }
  ],
  "variables": [
    {
      "dcid": "dc/v/VariableDcid",
      "places_with_data": ["geoId/06", "country/CAN", "..."]
    }
  ],
  "dcid_name_mappings": {
    "dc/t/TopicDcid": "Readable Topic Name",
    "dc/v/VariableDcid": "Readable Variable Name",
    "geoId/06": "California",
    "country/CAN": "Canada"
  },
  "dcid_place_type_mappings": {
    "geoId/06": ["State"],
    "country/CAN": ["Country"]
  },
  "status": "SUCCESS"
}

### How to Process the Response

  - `topics`: (Only if `include_topics=True`) Collections of variables and sub-topics. Use `dcid_name_mappings` to get readable names for presentation.

  - `variables`: Individual data indicators. Use `dcid_name_mappings` to get readable names.

  - `places_with_data`: (Only if `places` was in the request) A list of *DCIDs* for the requested places that have data for that specific indicator.

  - `dcid_name_mappings`: A dictionary mapping all DCIDs (topics, variables, and places) in the response to their human-readable names.

  - `dcid_place_type_mappings`: A dictionary mapping place DCIDs to their types (e.g., `["State"]`, `["Country"]`). Use this for child place type determination in `get_observations`.

  - `resolved_parent_place`: (Only if `parent_place` was in the request) The resolved node information for the parent place.

**Final Reminder:** Always treat results as *candidates*. You must filter and rank them based on the user's full context.
