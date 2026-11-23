FROM python:3.12.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pipeline/requirements.lock /app/pipeline/requirements.lock
RUN pip install --no-cache-dir -r /app/pipeline/requirements.lock
COPY pipeline/pyproject.toml /app/pipeline/pyproject.toml
COPY pipeline/src /app/pipeline/src
COPY pipeline/config.example.yaml /app/pipeline/config.yaml
RUN pip install --no-deps -e /app/pipeline
USER 10001:10001
ENTRYPOINT ["ossustain-pipeline"]
