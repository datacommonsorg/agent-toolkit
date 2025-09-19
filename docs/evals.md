# Running Evaluations

The `packages/datacommons-mcp/evals/` directory contains internal test agents built with the [Google Agent Development Kit (ADK)](https://github.com/google/adk-python/).

Their purpose is evaluation and regression testing of Data Commons MCP interactions.

## Setup

Set required environment variables:

1.  `DC_API_KEY`: Get from the [Data Commons website](https://datacommons.org/api/key).
2.  `GEMINI_API_KEY`: See [ADK instructions](https://google.github.io/adk-docs/get-started/quickstart/#env).

```bash
export DC_API_KEY="<your-dc-key>"
export GEMINI_API_KEY="<your-gemini-key>"
```

## Running Evals

Run the pytest evaluation suite.

```bash
uv run pytest -k "eval"
```

## Manual Agent Execution

Use the ADK runner for manual execution or debugging.


1.  ADK Web Runner (All Agents)

Starts a local web server for all agents in evals/.

```bash
# Run from repo root
uv run adk web ./packages/datacommons-mcp/evals/
```

2.  Command-line Agent Run (Single Agent)

Run a single agent directly.

```
# Example: run test_tool_agent from repo root
uv run adk run ./packages/datacommons-mcp/evals/test_tool_agent
```
