# Data Commons MCP Server

This is a Model Context Protocol server for fetching public information from Data Commons (datacommons.org or custom instances).

[Data Commons](https://datacommons.org) is an open knowledge repository that provides a unified view across multiple public data sets and statistics. 

## Quickstart

### Prerequisites

1.  A Data Commons API key. You can get one from [apikeys.datacommons.org](https://apikeys.datacommons.org/).
2.  `uv`. You can find installation instructions at [https://astral.sh/uv](https://astral.sh/uv).

### Configuration

For basic usage against datacommons.org, set the following required environment variable:
```
export DC_API_KEY=<your API key>
```

To use the server with a Custom Data Commons instance, set additional environment variables using an `.env` file.  For usage, see the [Data Commons MCP documentation](https://github.com/datacommonsorg/agent-toolkit/blob/main/docs/user_guide.md#custom-data-commons).

### Start the server 

Run the server with `uvx`. 

**Streamable HTTP**

This runs the server with Streamable HTTP on port 8080. You can access it at `http://localhost:8080/mcp`.

```bash
uvx datacommons-mcp serve http
```

**stdio**

```bash
uvx datacommons-mcp serve stdio
```
Note: Normally when you run locally over Stdio, your [MCP client](#clients) will automatically spawn a subprocess to start the server, so you don't need to run this separately.

## Clients

You can use any MCP-enabled agent/client to connect to the server. See your preferred client's documentation for how to configure it, using the commands listed above. 

To use [Google Gemini CLI](https://github.com/google-gemini/gemini-cli) or a sample [Google ADK](https://google.github.io/adk-docs/) agent from Data Commons, see the [Data Commons MCP documentation](https://github.com/datacommonsorg/agent-toolkit/blob/main/docs/user_guide.md). Or try it out with this [Google Colab notebook](https://colab.research.google.com/github/datacommonsorg/agent-toolkit/blob/main/notebooks/datacommons_mcp_tools_with_custom_agent.ipynb).
