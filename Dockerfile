FROM python:3.11-slim AS backend
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
COPY fixtures/ fixtures/
RUN pip install --no-cache-dir -e .
EXPOSE 8010
CMD ["uvicorn", "fuzzy_reconciler.api.app:app", "--host", "0.0.0.0", "--port", "8010"]
