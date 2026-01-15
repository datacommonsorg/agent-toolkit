FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy local package
COPY packages/datacommons-mcp /tmp/pkg

# Install from local directory
# We install fastapi explicitly to match the main Dockerfile's layering (optional but good practice)
RUN pip install --no-cache-dir "fastapi>=0.115.0" && \
    pip install --no-cache-dir /tmp/pkg

# Create non-root user
RUN groupadd --gid 1001 mcp && useradd -m --uid 1001 --gid 1001 --shell /bin/false mcp
USER mcp

ENV PORT=8080

# Health check
HEALTHCHECK CMD curl --fail -H "Accept: application/json" http://localhost:${PORT}/health || exit 1

# Start server
CMD ["sh", "-c", "datacommons-mcp serve http --host 0.0.0.0 --port ${PORT}"]
