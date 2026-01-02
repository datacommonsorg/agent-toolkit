FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build arguments for version and index (default to standard PyPI)
ARG MCP_VERSION
ARG PIP_INDEX_URL=https://pypi.org/simple/
ARG PIP_EXTRA_INDEX_URL=https://pypi.org/simple/

# Check if MCP_VERSION is set
RUN if [ -z "$MCP_VERSION" ]; then echo "MCP_VERSION is not set" && exit 1; fi

# Install from PyPI/TestPyPI
RUN pip install --no-cache-dir \
    --index-url ${PIP_INDEX_URL} \
    --extra-index-url ${PIP_EXTRA_INDEX_URL} \
    datacommons-mcp==${MCP_VERSION}

# Create non-root user
RUN useradd -m mcp
USER mcp

ENV PORT=8080

# Health check with Accept header and explicit PORT
HEALTHCHECK CMD curl --fail -H "Accept: application/json" http://localhost:${PORT}/health || exit 1

# Use sh -c for variable expansion
CMD ["sh", "-c", "datacommons-mcp serve http --host 0.0.0.0 --port ${PORT}"]