# Data Commons MCP Server

This is a Model Context Protocol server for fetching public information from any Data Commons instance.

[Data Commons](https://datacommons.org) is an open knowledge repository that provides a unified view across multiple public data sets and statistics.  This server acts as a bridge, allowing any MCP-enabled agent or client to query this vast repository.

## Features
* MCP-Compliant: Implements the Model Context Protocol for seamless agent integration.
* Data Commons Access: Fetches public statistics and data from the base datacommons.org knowledge graph.
* Custom Instance Support: Can be configured to work with Custom Data Commons instances.
* Flexible Serving: Runs over both streamable HTTP and stdio.

## Quickstart

### Prerequisites

1.  You must have a Data Commons API key; create one at [apikeys.datacommons.org](https://apikeys.datacommons.org/).
2.  Install `uv` by following the [official installation instructions](https://github.com/astral-sh/uv#installation).

### Configuration

Set the following required environment variable in your shell:

```
export DC_API_KEY=<your API key>
```

### Start the server 

Run the server from your command line in one of two modes:

**Streamable HTTP**

This runs the server with Streamable HTTP, defaulting to port 8080.

```bash
uvx datacommons-mcp serve http
```
You can specify a different port with the --port argument:
```bash
uvx datacommons-mcp serve http --port <port>
```

The server will be available at http://localhost:<port>/mcp.

**stdio**

```bash
uvx datacommons-mcp serve stdio
```
Note: Normally, an MCP client will automatically spawn this subprocess, so you may not need to run this command manually.

## Clients

You can use any MCP-enabled agent or client to connect to your running server. For example, see the [Data Commons MCP documentation](https://github.com/datacommonsorg/agent-toolkit/blob/main/docs/user_guide.md) for guides on connecting:
* [Google Gemini CLI](https://github.com/datacommonsorg/agent-toolkit/blob/main/docs/quickstart.md)
* [Google ADK natively](https://github.com/datacommonsorg/agent-toolkit/blob/main/docs/user_guide.md#use-the-sample-agent)
* [Google ADK in Colab](https://colab.research.google.com/github/datacommonsorg/agent-toolkit/blob/main/notebooks/datacommons_mcp_tools_with_custom_agent.ipynb)

Or see your preferred client's documentation for how to configure it, using the commands listed above.

## Advanced Configuration
### Using MCP Tools with a Custom Data Commons

Follow the [Guide for using MCP Tools with Custom Data Commons](https://github.com/datacommonsorg/agent-toolkit/blob/main/docs/user_guide.md#custom-data-commons) to set additional environment variables required for custom configuration.
