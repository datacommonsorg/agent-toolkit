FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir datacommons-mcp

ENV PORT=8080
HEALTHCHECK CMD curl --fail http://localhost:8080/health || exit 1

CMD ["datacommons-mcp", "serve", "http", "--host", "0.0.0.0", "--port", "8080"]