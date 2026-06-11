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

* **Mode Selection**:
    * To get data for the specified place (e.g., California), **do not** provide `child_place_type`.
    * To get data for all its children (e.g., all counties in California), you **must also** provide the `child_place_type` (e.g., "County").
      **CRITICAL:** Before calling `get_observations` with `child_place_type`, you **MUST** first call `search_indicators` with child sampling to determine the correct child place type.
      **Child Type Determination Logic:**
      1. Use the `dcid_place_type_mappings` or inline `typeOf` fields from the `search_indicators` response to examine the types of sampled child places
      2. Use the type that is common to ALL sampled child places
      3. If more than one type is common to all child places, use the most specific type
      4. If there is no common type across all sampled child places, use the majority type (50%+ threshold) if there's a clear majority
      5. If there is no common type and no clear majority, this tool cannot be called with child-place mode - fall back to single-place mode `get_observations` calls for each place
      **Note:** If you used child sampling in `search_indicators` to validate variable existence, you should still get data for ALL children of that type, not just the sampled subset.

* **Data Volume Constraint**: When using **Child Places Mode** (when `child_place_type` is set), you **must** be conservative with your date range to avoid requesting too much data.
    * Avoid requesting `'all'` data via the `date` parameter.
    * **Instead, you must either request the `'latest'` data or provide a specific, bounded date range.**

* **Date Filtering**: The tool filters observations by date using the following priority:
    1.  **`date`**: The `date` parameter is optional and can be one of the values 'all', 'latest', 'range', or a date string in the format 'YYYY', 'YYYY-MM', or 'YYYY-MM-DD'.
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
    The fetched observation data directly from Data Commons.
    The response format contains:
    - `variable`: Details about the statistical variable requested (dcid, name, typeOf).
    - `resolvedParentPlace`: The resolved node information for the parent place, if one was provided.
    - `childPlaceType`: The place type of the children observations if ContainedIn mode was used.
    - `placeObservations`: A list of observations, one entry per place. Each entry contains:
        - `place`: Details about the observed place (dcid, name, typeOf).
        - `timeSeries`: A list of point objects containing `{"date": "...", "value": ...}` where value is a number.
    - `sourceMetadata`: Information about the primary data source used (sourceId, importName, measurementMethod, unit, etc.).
    - `alternativeSources`: Details about other available data sources.
