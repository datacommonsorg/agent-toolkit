# Data Commons MCP Server

This is an experimental MCP server for fetching public information from [Data Commons](https://datacommons.org/).

**This is experimental and subject to change.**

## Requirements

1.  A Data Commons API key. You can get one from [apikeys.datacommons.org](https://apikeys.datacommons.org/).
2.  `uv`. You can find installation instructions at [https://astral.sh/uv](https://astral.sh/uv).

## Configuration

The server can be configured using environment variables. For local development, you can copy [`.env.sample`](.env.sample) to `.env` and edit the values.
Note that the `.env` file should be in your current working directory:

```bash
cp .env.sample .env
# Edit .env with your configuration
```

The `.env.sample` file contains all available configuration options with detailed documentation. Only `DC_API_KEY` is required; `DC_TYPE` defaults to "base" if not specified.

## Getting Started

Run the server with `uvx`. You can set the API key via environment variable or use a `.env` file:

**stdio**

```bash
# Using environment variable
DC_API_KEY=<your-key> uvx datacommons-mcp serve stdio

# Or using .env file (copy .env.sample to .env first)
uvx datacommons-mcp serve stdio
```

**Streamable http**

This will run the server with Streamable HTTP on port 8080. You can access it at `http://localhost:8080/mcp`.

```bash
# Using environment variable
DC_API_KEY=<your-key> uvx datacommons-mcp serve http

# Or using .env file
uvx datacommons-mcp serve http
```

**Debugging**

You can start the MCP inspector on port 6277. Look at the output for the pre-filled proxy auth token URL.

```bash
# Using environment variable
DC_API_KEY=<your-key> npx @modelcontextprotocol/inspector uvx datacommons-mcp serve stdio

# Or using .env file
npx @modelcontextprotocol/inspector uvx datacommons-mcp serve stdio
```

> IMPORTANT: Open the inspector via the **pre-filled session token url** which is printed to terminal on server startup.
> * It should look like `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN={session_token}`

Then to connect to this MCP server, enter the following values in the inspector UI:

- Transport Type: `STDIO`
- Command: `uvx`
- Arguments: `datacommons-mcp serve stdio`

Click `Connect`

## Testing with Gemini CLI

You can use this MCP server with the [Gemini CLI](https://github.com/google-gemini/gemini-cli).

Edit your `~/.gemini/settings.json` file and add the following, replacing `<your api key>` with your actual API key:

```json
{
  ...
  "mcpServers": {
    "datacommons-mcp": {
      "command": "uvx",
      "args": [
        "datacommons-mcp",
        "serve",
        "stdio"
      ],
      "env": {
        "DC_API_KEY": "<your api key>"
      },
      "trust": true
    }
  }
}
```

# Development

## Running Evaluations

The `evals/` directory contains internal test agents built with the [Google Agent Development Kit (ADK)](https://github.com/google/adk-python/).

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
