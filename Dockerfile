FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Install project once; volumes only hold data, never overwrite source or installed packages.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY reports/real-data ./reports/real-data
COPY docker/ ./docker/
RUN mkdir -p /app/data_store && chmod +x /app/docker/mcp-entrypoint.sh

EXPOSE 8001 8501
