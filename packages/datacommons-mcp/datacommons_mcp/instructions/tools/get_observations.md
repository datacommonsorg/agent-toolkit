Retrieve time-series numerical observations for a specific statistical variable at a target place. Returns an array of dated observation values and their source metadata. Operates in single-place mode; for child-level containment data, use get_child_observations.

Only call this with a `variable_dcid` returned by a search tool (`search_indicators` or `search_child_indicators`). Never guess, assume, or construct a DCID from memory or from similar-looking DCIDs.
