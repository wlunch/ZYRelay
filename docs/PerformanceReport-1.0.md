# ZYRelay 1.0 Performance Report

**Run date:** 2026-08-10  
**Runtime:** local macOS ARM64, Python 3.13.7, `.venv-paddleocr`  
**Command:** `python benchmark/scripts/run_benchmark.py --suite contract --output benchmark/results/v1_validation`

| Metric | Result |
| --- | ---: |
| Cases completed / partial | 6 / 6 |
| Mean end-to-end runtime | 4,417 ms |
| Runtime range | 3,582–5,190 ms |
| Mean traced Python peak memory | 9.3 MB |
| Peak traced Python memory range | 1.1–27.4 MB |
| Evidence valid rate | 100% |
| Provenance valid rate | 100% |
| Offline test coverage | 84% |

The benchmark also writes model execution/skip data for layout, OCR,
classifier, language, NER, code detection, spelling and table resources. This
is a local engineering benchmark, not a universal accuracy claim. The observed
mean expected-item recall (75%), semantic-evidence completeness (67%) and the
current 84% whole-package coverage are below the 95% release target. The suite
includes scanned and fallback scenarios, while optional model runtime modules
remain intentionally untested offline. These are explicit release follow-ups,
not results masked by model output.
