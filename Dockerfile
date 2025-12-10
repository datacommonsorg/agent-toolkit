FROM python:3.11-slim

# Prevent python from buffering stdout/stderr (helps with logging)
ENV PYTHONUNBUFFERED=1

# Install the package
RUN pip install --no-cache-dir datacommons-mcp

# Expose the port
ENV PORT=8080

# HEALTHCHECK: Basic check to ensure the server is responsive
# This helps Cloud Run know if the container is zombie
HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1

# THE COMMAND
# 1. Bind to 0.0.0.0 (Crucial for Cloud Run)
# 2. Bind to the environment variable PORT
CMD ["datacommons-mcp", "serve", "http", "--host", "0.0.0.0", "--port", "8080"]