# Ground System

GroundChoose resolves the applicable enterprise ground before parsing. YAML
files under `config/ground/` and `config/ground_truth/` contain labels, aliases,
business objects, convention rules and profiles. They are versioned in Git and
materialized as an immutable ground snapshot for every execution.

The UOM `processing.configuration` section records the version and SHA-256 hash
of labels, business objects, rule patterns, models, languages and thresholds.
Change YAML through review; Relay never learns or rewrites ground truth itself.
