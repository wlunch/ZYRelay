# Default enterprise resource profile

This profile is versioned configuration, not executable business code. Resource
selection is deterministic: defaults, then `environment`, `department`, `team`,
and finally `project` overlays. Every chosen resource and fallback is written to
the ResourcePlan and its provenance record.
