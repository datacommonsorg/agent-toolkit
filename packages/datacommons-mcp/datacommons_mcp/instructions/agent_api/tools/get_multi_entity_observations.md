Fetches time-series observations for multi-entity relationship statistical variables (e.g. foreign aid flows, bilateral trade, international migration).

### Parameters
- `variable_dcid` (required, string): Statistical variable DCID (e.g., `"Amount_EconomicActivity_GrossODA"`).
- `entities` (required, dictionary of string lists): Map of entity property names to list of entity DCIDs (e.g. `{"donor": ["country/ARE"], "recipient": ["country/AFG"]}`).
- `parent_entity_property` (optional, string): Entity property name for child place expansion (e.g. `"recipient"`).
- `parent_entity_dcid` (optional, string): Parent place DCID for child place expansion (e.g. `"Earth"`).
- `child_entity_type` (optional, string): Child place type for child place expansion (e.g. `"Country"`).
- `source_override` (optional, string): Filter by a specific data source provenance DCID.
- `date` (optional, string): Specific date (e.g., `"2024"`), `"all"` (for complete historical time series), or `"latest"` (default).
- `date_range_start` / `date_range_end` (optional, string): Date range boundaries.

*Important: `parent_entity_property`, `parent_entity_dcid`, and `child_entity_type` are co-dependent. If requesting child expansion, all three must be specified together.*

### Usage Example (Direct Bilateral Pair)
```json
{
  "variable_dcid": "Amount_EconomicActivity_GrossODA",
  "entities": {
    "donor": ["country/ARE"],
    "recipient": ["country/AFG"]
  }
}
```

### Usage Example (Child Entity Expansion)
```json
{
  "variable_dcid": "Amount_EconomicActivity_GrossODA",
  "entities": {
    "donor": ["country/ARE"]
  },
  "parent_entity_property": "recipient",
  "parent_entity_dcid": "Earth",
  "child_entity_type": "Country"
}
```
