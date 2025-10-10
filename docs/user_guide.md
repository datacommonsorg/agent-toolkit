# Data Commons MCP User Guide

## Overview

The [Data Commons](https://datacommons.org) [Model Context Protocol (MCP)](https://modelcontextprotocol.io/docs/getting-started/intro) service gives AI agents access to the Data Commons knowledge graph and returns data related to statistical variables, topics, and observations. It allows end users to formulate complex natural-language queries interactively, get data in textual, structured or unstructured formats, and download the data as desired. For example, depending on the agent, a user can answer high-level questions such as "give me the economic indicators of the BRICS countries", view simple tables, and download a CSV file of the data in tabular format.

The MCP server returns data from datacommons.org by default or can be configured for a Custom Data Commons instance. 

The server is a Python binary based on the [FastMCP 2.0 framework](https://gofastmcp.com). A prebuilt package is available at https://pypi.org/project/datacommons-mcp/.

At this time, there is no centrally deployed server; you run your own server, and any client you want to connect to it.

![alt text](mcp.png)

### Tools

The server currently supports the following tools:

- `search_indicators`: Searches for available variables and/or topics (a hierarchy of sub-topics and member variables) for a given place or metric. Topics are only relevant for Custom Data Commons instances that have implemented them.
- `get_observations`: Fetches statistical data for a given variable and place.
- `validate_child_place_types`: Validates child place types for a given parent place.

> Tip: If you want a deeper understanding of how the tools work, you may use the [MCP Inspector](https://modelcontextprotocol.io/legacy/tools/inspector) to make tool calls directly; see [Test with MCP Inspector](#test-with-mcp-inspector) for details.

### Clients

To connect to the Data Commons MCP Server, you can use any available AI application that supports MCP, or your own custom agent. 

The server supports both standard MCP [transport protocols](https://modelcontextprotocol.io/docs/learn/architecture#transport-layer):
- Stdio: For clients that connect directly using local processes
- Streamable HTTP: For clients that connect remotely or otherwise require HTTP (e.g. Typescript)

See [Basic usage](#basic-usage) below for how to use the server with Google-based clients over Stdio.

For an end-to-end tutorial using a server and agent over HTTP in the cloud, see the sample Data Commons Colab notebook, [Try Data Commons MCP Tools with a Custom Agent](https://github.com/datacommonsorg/agent-toolkit/blob/main/notebooks/datacommons_mcp_tools_with_custom_agent.ipynb).

### Unsupported features

At the current time, the following are not supported:
- Non-geographical ("custom") entities
- Events
- Exploring nodes and relationships in the graph

## Basic usage

This section shows you how to run a local agent that kicks off the server in a subprocess.

We provide specific instructions for the following agents:
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) -- best for playing with the server; requires minimal setup. See the [Quickstart](quickstart.md) for this option.
- A sample basic agent based on the Google [Agent Development Kit](https://google.github.io/adk-docs/) and [Gemini Flash 2.5](https://deepmind.google/models/gemini/flash/) -- best for interacting with a sample ADK-based web agent; requires some additional setup. See below for this option.

For other clients/agents, see the relevant documentation; you should be able to reuse the commands and arguments detailed below.

### Prerequisites

For all instances:

- A Data Commons API key. To obtain an API key, go to <https://apikeys.datacommons.org> and request a key for the `api.datacommons.org` domain.
- For running the sample agent or the Colab notebook, a GCP project and a Google AI API key. For details on supported keys, see <https://google.github.io/adk-docs/get-started/quickstart/#set-up-the-model>.
- For running the sample agent locally, or running the server locally in standalone mode, install `uv` for managing and installing Python packages; see the instructions at <https://docs.astral.sh/uv/getting-started/installation/>. 
- For running the sample agent locally, install [Git](https://git-scm.com/).

> **Important**: Additionally, for custom Data Commons instances:

> If you have not rebuilt your Data Commons image since the stable release of 2025-09-08, you must [sync to the latest stable release](https://docs.datacommons.org/custom_dc/build_image.html#sync-code-to-the-stable-branch), [rebuild your image](https://docs.datacommons.org/custom_dc/build_image.html#build-package) and [redeploy](https://docs.datacommons.org/custom_dc/deploy_cloud.html#manage-your-service).

### Configure environment variables

#### Base Data Commons (datacommons.org)

For basic usage against datacommons.org, set the required `DC_API_KEY` in your shell/startup script (e.g. `.bashrc`).
```bash
export DC_API_KEY=<your API key>
```

#### Custom Data Commons

If you're running a against a custom Data Commons instance, we recommend using a `.env` file, which the server locates automatically, to keep all the settings in one place. All supported options are documented in https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/.env.sample. 

To set variables using a `.env` file:

1. From Github, download the file [`.env.sample`](https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/.env.sample) to the desired directory. Or, if you plan to run the sample agent, clone the repo https://github.com/datacommonsorg/agent-toolkit/.

1. From the directory where you saved the sample file, copy it to a new file called `.env`. For example:
   ```bash
   cd ~/agent-toolkit/packages/datacommons-mcp
   cp .env.sample .env
   ```
1. Set the following variables: 
   - `DC_API_KEY`: Set to your Data Commons API key
   - `DC_TYPE`: Set to `custom`.
   - `CUSTOM_DC_URL`: Uncomment and set to the URL of your instance. 
1. Optionally, set other variables.
1. Save the file.

### Use the sample agent

We provide a basic agent for interacting with the MCP Server in [packages/datacommons-mcp/examples/sample_agents/basic_agent](https://github.com/datacommonsorg/agent-toolkit/tree/main/packages/datacommons-mcp/examples/sample_agents/basic_agent). To run the agent locally:

1. If not already installed, install `uv` for managing and installing Python packages; see the instructions at <https://docs.astral.sh/uv/getting-started/installation/>. 
1. From the desired directory, clone the `agent-toolkit` repo:
   ```bash
   git clone https://github.com/datacommonsorg/agent-toolkit.git
   ```
1. Set the following environment variables in your shell or startup script:
   ```bash
   export DC_API_KEY=<your Data Commons API key>
   export GEMINI_API_KEY=<your Google AI API key>
   ```
1. Go to the root directory of the repo:
   ```bash
   cd agent-toolkit
   ```
1. Run the agent using one of the following methods.

#### Web UI (recommended):

1. Run the following command:
   ```bash
   uvx --from google-adk adk web ./packages/datacommons-mcp/examples/sample_agents/
   ```
1. Point your browser to the address and port displayed on the screen (e.g. `http://127.0.0.1:8000/`). The Agent Development Kit Dev UI is displayed. 
1. From the **Type a message** box, type your query for Data Commons or select another action.

#### Command line interface

1. Run the following command:
   ```bash
   uvx --from google-adk adk run ./packages/datacommons-mcp/examples/sample_agents/basic_agent
   ```
1. Enter your queries at the `User` prompt in the terminal.

## Develop your own ADK agent

We provide two sample Google Agent Development Kit-based agents you can use as inspiration for building your own agent:

- [Try Data Commons MCP Tools with a Custom Agent](https://github.com/datacommonsorg/agent-toolkit/blob/main/notebooks/datacommons_mcp_tools_with_custom_agent.ipynb) is a Google Colab tutorial that shows how to build an ADK Python agent step by step. 
- The sample [basic agent](https://github.com/datacommonsorg/agent-toolkit/tree/main/packages/datacommons-mcp/examples/sample_agents/basic_agent) is a simple Python ADK agent you can use to develop locally. At the most basic level, you can modify its configuration, including:
   - The [AGENT_INSTRUCTIONS](https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/examples/sample_agents/basic_agent/instructions.py)
   - The [AGENT_MODEL](https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/examples/sample_agents/basic_agent/agent.py#L23)
   - The transport layer protocol: see [Connect to a remote server](#sample-agent) for details.

   To run the custom code, see [Use the sample agent](#use-the-sample-agent) above.

### Test with MCP Inspector

If you're interested in getting a deeper understanding of Data Commons tools and API, the [MCP Inspector](https://modelcontextprotocol.io/legacy/tools/inspector) is a useful web UI for interactively sending tool calls to the server using JSON messages. It runs locally and spawns a server. It uses token-based OAuth for authentication, which it generates itself, so you don't need to specify any keys.

To use it:

1. If not already installed on your system, install [`node.js`](https://nodejs.org/en/download) and [`uv`](https://docs.astral.sh/uv/getting-started/installation/).
1. Ensure you've set up the relevant server [environment variables](#environment-variables). If you're using a `.env` file, go to the directory where the file is stored.
1. Run:
   ```
   npx @modelcontextprotocol/inspector uvx datacommons-mcp serve stdio
   ```
1. Open the Inspector via the pre-filled session token URL which is printed to terminal on server startup. It should look like `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=<session token>`. 
1. Click on the link to open the browser. The tool is prepopulated with all relevant variables.
1. In the far left pane, click **Connect**. 
1. Click the **Tools** button to display the Data Commons tools and prompts.
1. In the left pane, select a tool. 
1. In the right pane, scroll below the prompts to view the input form.
1. Enter values for required fields and click **Run Tool**. Data are shown in the **Tool Result** box.

## Use a remote server/client

### Run a standalone server

1. Ensure you've set up the relevant server [environment variables](#environment-variables). If you're using a `.env` file, go to the directory where the file is stored.
1. Run:
   ```bash
   uvx datacommons-mcp serve http [--port <port>]
   ```
By default, the port is 8080 if you don't set it explicitly.

The server is addressable with the endpoint `mcp`. For example, `http://my-mcp-server:8080/mcp`.

### Connect to an already-running server from a remote client

Below we provide instructions for Gemini CLI and a sample ADK agent. If you're using a different client, consult its documentation to determine how to specify an HTTP URL.

#### Gemini CLI

To configure Gemini CLI to connect to a remote Data Commons server over HTTP, replace the `mcpServers` section in `~/.gemini/settings.json` (or other `settings.json` file) with the following:

```json
{
// ...
"mcpServers": {
    "datacommons-mcp": {
      "httpUrl": "http://<host>:<port>/mcp"
    }
    // ...
  }
}
```
#### Sample agent

To configure the sample agent to connect to a remote Data Commons MCP server over HTTP, you need to modify the code in [`basic_agent/agent.py`](https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/examples/sample_agents/basic_agent/agent.py).  Set import modules and agent initialization parameters as follows:

```python
# ...
from google.adk.tools.mcp_tool.mcp_toolset import (
   MCPToolset,
   StreamableHTTPConnectionParams
)
#...
   LlmAgent(
      # ...
      tools=[McpToolset(
         connection_params=StreamableHTTPConnectionParams(
            url=f"http://<host>:<port>/mcp"
         )
      )],
   )
```
Run the agent as described in [Use the sample agent](#use-the-sample-agent) above.

## Feedback
We use [Google Issue Tracker](https://issuetracker.google.com/) to track bugs and feature requests. All tickets are publicly viewable.

Before opening a new ticket, please see if an existing [feature request](https://issuetracker.google.com/issues?q=componentid:1659535%2B%20type:feature_request) or [bug report](https://issuetracker.google.com/issues?q=componentid:1659535%20type:bug) covering your issue has already been filed. If yes, upvote (by clicking the '+1' button) and subscribe to it. If not, open a new [feature request](https://issuetracker.google.com/issues/new?component=1659535&template=2053233) or [bug report](https://issuetracker.google.com/issues/new?component=1659535&template=2053231).

For any issue you file, make sure to indicate that it affects the Data Commons MCP Server.

## Disclaimer
AI applications using the MCP server can make mistakes, so please double-check responses.
