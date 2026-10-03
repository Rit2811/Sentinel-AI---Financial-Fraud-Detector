FROM python:3.12.13-slim
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.2
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --extra worker --no-dev --no-install-project --no-cache
COPY src ./src
RUN uv sync --locked --extra worker --no-dev --no-editable --no-cache
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["/app/.venv/bin/python", "-m", "fraud_ml.worker"]
