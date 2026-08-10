# Model Routing and Enterprise Profiles

v0.7 adds a deterministic `ModelRouter` before each optional local model. It records `run` or `skip`, reason, input signals and selected resource in both `ResourcePlan` and `ModelExecution`.

| Capability | Runs when | Skips when |
| --- | --- | --- |
| OCR | scanned PDF and `enable_ocr=true` | DOCX, native-text PDF, request disabled |
| Layout | PDF heuristic, or visual layout is requested/scanned | DOCX logical blocks are sufficient |
| Table | table block exists or visual detection requested | no table signal |
| Classifier | Relay mode is `auto` | mode already identifies the document purpose |
| Language | no `language_hint` | caller supplied language hint |
| NER | rule labels did not produce entities | governed entity labels already exist |
| Code detection | code-convention mode or source signal | no code signal |
| Spell correction | OCR generated text | native parser text |

Enterprise profiles are overlays on `config/enterprises/default/resources.yaml`. For example, `enterprise-a` selects the local AI primary resources, while `enterprise-b` uses heuristic layout and disables NER without changing the Relay pipeline.

```bash
python -m zyrelay.models warmup
zyrelay benchmark compare-models \
  --left-file benchmark/results/baseline/CASE/models.json \
  --right-file benchmark/results/latest/CASE/models.json \
  --left-resource noop-ocr --right-resource paddleocr
```

Warmup loads only already verified local resources and never downloads a package or weight.
