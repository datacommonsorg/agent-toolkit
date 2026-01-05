# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build arguments for version and index (default to standard PyPI)
ARG MCP_VERSION
ARG PIP_INDEX_URL=https://pypi.org/simple/
ARG PIP_EXTRA_INDEX_URL=https://pypi.org/simple/

# Check if MCP_VERSION is set
RUN if [ -z "$MCP_VERSION" ]; then echo "MCP_VERSION is not set" && exit 1; fi

# Install packages in a single layer
# 1. Pre-install fastapi from PyPI to avoid TestPyPI squatting
# 2. Install main package
# Note: We must explicitly unset PIP_EXTRA_INDEX_URL for the first command to force PyPI usage.
RUN PIP_EXTRA_INDEX_URL="" pip install --no-cache-dir "fastapi>=0.115.0" --index-url https://pypi.org/simple/ && \
    pip install --no-cache-dir \
    --index-url ${PIP_INDEX_URL} \
    --extra-index-url ${PIP_EXTRA_INDEX_URL} \
    datacommons-mcp==${MCP_VERSION}

# Create non-root user with explicit UID/GID and disabled shell
RUN groupadd --gid 1001 mcp && useradd -m --uid 1001 --gid 1001 --shell /bin/false mcp
USER mcp

ENV PORT=8080

# Health check with Accept header and explicit PORT
HEALTHCHECK CMD curl --fail -H "Accept: application/json" http://localhost:${PORT}/health || exit 1

# Use sh -c for variable expansion
CMD ["sh", "-c", "datacommons-mcp serve http --host 0.0.0.0 --port ${PORT}"]
