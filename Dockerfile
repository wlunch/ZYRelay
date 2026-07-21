FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ZYRELAY_DATA_ROOT=/app/data

WORKDIR /app

COPY pyproject.toml README.md ./
COPY zyrelay ./zyrelay
COPY config ./config
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data/documents /app/data/doc_prepare /app/data/doc_index

EXPOSE 8000

CMD ["uvicorn", "zyrelay.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
