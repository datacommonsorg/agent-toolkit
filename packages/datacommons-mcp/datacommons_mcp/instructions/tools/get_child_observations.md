Retrieve time-series numerical observations for a statistical variable across all child places of a specific type within a parent geographic entity. Returns an array of dated observation values for each child place and their source metadata. Requires specifying the child place type (e.g., 'County' or 'State') and a bounded date range or 'latest' filter to prevent payload saturation.

Only call this with a `variable_dcid` returned by a search tool (`search_indicators` or `search_child_indicators`). Never guess, assume, or construct a DCID from memory or from similar-looking DCIDs.
