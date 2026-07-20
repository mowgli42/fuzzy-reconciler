FROM python:3.11-slim AS backend
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
COPY src/ src/
EXPOSE 8000
CMD ["uvicorn", "src.fuzzy_reconciler.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
