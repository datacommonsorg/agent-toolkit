Fetches observations for a statistical variable from Data Commons.

**CRITICAL: Always validate variable-place combinations first**
- You **MUST** call `search_indicators` first to verify that the variable exists for the specified place
- Only use DCIDs returned by `search_indicators` - never guess or assume variable-place combinations
- This ensures data availability and prevents errors from invalid combinations

This tool can operate in two primary modes:
1.  **Single Place Mode**: Get data for one specific place (e.g., "Population of California").
2.  **Child Places Mode**: Get data for all child places of a certain type within a parent place (e.g., "Population of all counties in California").

### Core Logic & Rules

* **Variable Selection**: You **must** provide the `variable_dcid`.
    * Variable DCIDs are unique identifiers for statistical variables in Data Commons and are returned by prior calls to the
    `search_indicators` tool.

* **Place Selection**: You **must** provide the `place_dcid`.
    * **Important Note for Bilateral Data**: When fetching data for bilateral variables (e.g., exports from one country to another),
    the `variable_dcid` often encodes one of the places (e.g., `TradeExports_FRA` refers to exports *to* France).
    In such cases, the `place_dcid` parameter in `get_observations` should specify the *other* place involved in the bilateral relationship
    (e.g., the exporter country, such as 'USA' for exports *from* USA).
    The `search_indicators` tool's `places_with_data` field can help identify which place is the appropriate observation source for `place_dcid`.

* **Mode Selection**:
    * To get data for the specified place (e.g., California), **do not** provide `child_place_type`.
    * To get data for all its children (e.g., all counties in California), you **must also** provide the `child_place_type` (e.g., "County").
      **CRITICAL:** Before calling `get_observations` with `child_place_type`, you **MUST** first call `search_indicators` with child sampling to determine the correct child place type.
      **Child Type Determination Logic:**
      1. Use the `dcid_place_type_mappings` field from the `search_indicators` response to examine the types of sampled child places
      2. Use the type that is common to ALL sampled child places
      3. If more than one type is common to all child places, use the most specific type
      4. If there is no common type across all sampled child places, use the majority type (50%+ threshold) if there's a clear majority
      5. If there is no common type and no clear majority, this tool cannot be called with child-place mode - fall back to single-place mode `get_observations` calls for each place
      **Note:** If you used child sampling in `search_indicators` to validate variable existence, you should still get data for ALL children of that type, not just the sampled subset.

* **Data Volume Constraint**: When using **Child Places Mode** (when `child_place_type` is set), you **must** be conservative with your date range to avoid requesting too much data.
    * Avoid requesting `'all'` data via the `date` parameter.
    * **Instead, you must either request the `'latest'` data or provide a specific, bounded date range.**

* **Date Filtering**: The tool filters observations by date using the following priority:
    1.  **`date`**: The `date` parameter is required and can be one of the enum values 'all', 'latest', 'range', or a date string in the format 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'.
    2.  **Date Range**: If `date` is set to 'range', you must specify a date range using `date_range_start` and/or `date_range_end`.
        * If only `date_range_start` is specified, then the response will contain all observations starting at and after that date (inclusive).
        * If only `date_range_end` is specified, then the response will contain all observations before and up to that date (inclusive).
        * If both are specified, the response contains observations within the provided range (inclusive).
        * Dates must be in `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` format.
    3.  **Default Behavior**: If you do not provide **any** date parameters (`date`, `date_range_start`, or `date_range_end`), the tool will automatically fetch only the `'latest'` observation.

Args:
  variable_dcid (str, required): The unique identifier (DCID) of the statistical variable.
  place_dcid (str, required): The DCID of the place.
  child_place_type (str, optional): The type of child places to get data for. **Use this to switch to Child Places Mode.**
  source_override (str, optional): An optional source ID to force the use of a specific data source.
  date (str, optional): An optional date filter. Accepts 'all', 'latest', 'range', or single date values of the format 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'. Defaults to 'latest' if no date parameters are provided.
  date_range_start (str, optional): The start date for a range (inclusive). **Used only if `date` is set to'range'.**
  date_range_end (str, optional): The end date for a range (inclusive). **Used only if `date` is set to'range'.**

Returns:
    The fetched observation data including:
    - `variable`: Details about the statistical variable requested.
    - `place_observations`: A list of observations, one entry per place. Each entry contains:
        - `place`: Details about the observed place (DCID, name, type).
        - `time_series`: A list of `(date, value)` tuples, where `date` is a string (e.g., "2022-01-01") and `value` is a float.
    - `source_metadata`: Information about the primary data source used.
    - `alternative_sources`: Details about other available data sources.
