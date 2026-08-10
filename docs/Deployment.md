# Deployment

Requirements: Python 3.11+ or Docker. The lean image contains the deterministic
pipeline and graceful heuristic fallbacks; optional local model resources use
`data/model_cache/` and remain disabled until available.

```bash
docker compose up --build
# then open http://127.0.0.1:8000/docs
```

For a local developer install: `python -m pip install -e '.[dev]'`, then
`uvicorn zyrelay.app.main:app --host 0.0.0.0 --port 8000`. Persistent artifacts
are stored under `data/`; mount that directory in production. Set file-size and
data-root settings through `ZYRELAY_MAX_FILE_SIZE` and `ZYRELAY_DATA_ROOT`.
