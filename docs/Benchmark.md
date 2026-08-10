# Benchmark Framework

`benchmark/` contains versioned cases and expected criteria for contracts,
code conventions, policies, API specifications and scanned documents. Run:

```bash
python benchmark/scripts/run_benchmark.py --suite contract --output benchmark/results/latest
```

The report captures extraction checks, rule/entity recall, semantic evidence
completeness, OCR checks, model execution and skip counts, runtime, peak Python
memory, warnings, and per-plugin execution comparison. Results are local JSON
artifacts suitable for regression comparison; they are not a claim of universal
model accuracy.
