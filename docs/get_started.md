# Get Started with Data Commons MCP Tools

## Overview

The Data Commons Model Context Protocol (MCP) tools give AI agents access to the Data Commons knowledge graph and returns data related to statistical variables, topics, and observations. It allows end users to formulate complex natural-language queries interactively, get data in textual, structured or unstructured formats, and download the data as desired. For example, depending on the agent, a user can answer high-level questions such as "give me the economic indicators of the BRICS countries", view simple tables, and download a CSV file of the data in tabular format.

The MCP server returns data from datacommons.org by default or can be configured for a Custom Data Commons instance. 

The server is a Python binary based on the [FastMCP 2.0 framework](https://gofastmcp.com). It runs in a Python virtual environment. A prebuilt package is available at https://pypi.org/project/datacommons-mcp/.

At this time, there is no centrally deployed server; you run your own server, and any client you want to connect to it.

![alt text](mcp.png)

### Tools

The server currently supports the following tools:

- `search_indicators`: Searches for available variables and/or topics (a hierarchy of sub-topics and member variables) for a given place or metric. Topics are only relevant for Custom Data Commons instances that have implemented them.
- `get_observations`: Fetches statistical data for a given variable and place.
- `validate_child_place_types`: Validates child place types for a given parent place.

Tool APIs are defined in [packages/datacommons-mcp/datacommons_mcp/server.py](https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/datacommons_mcp/server.py). 

> Tip: If you want a deeper understanding of how the tools work, you may use the [MCP Inspector](https://modelcontextprotocol.io/legacy/tools/inspector) to make tool calls directly; see [Test with MCP Inspector](#test-with-mcp-inspector) for details.

### Clients

To connect to the Data Commons MCP Server, you can use any available AI application that supports MCP, or your own custom agent. 

The server supports both standard MCP transport protocols:
- Stdio: For clients that connect directly using local processes
- Streamable HTTP: For clients that connect remotely or otherwise require HTTP (e.g. Typescript)

See [Basic usage](#basic-usage) below for how to use the server with Google-based clients over Stdio.

For an end-to-end tutorial using a server and agent over HTTP in the cloud, see the sample Data Commons [Colab notebook]().

### Unsupported features

At the current time, the following are not supported:
- Non-geographical ("custom") entities
- Events
- Exploring nodes and relationships in the graph

### Feedback

If you'd like to provide feedback on the Data Commons MCP tools, please see this [FAQ entry](https://datacommons.org/faq#:~:text=Q%3A%20How%20can%20I%20send%20feedback%20about%20Data%20Commons%3F) on how to file bugs or feature requests. 

## Basic usage

This section shows you how to run a local agent that kicks off the server in a subprocess.

Below we provide specific instructions for the following agents:
- [Gemini CLI](https://github.com/google-gemini/gemini-cli) -- best for playing with the server; requires minimal setup.
- A sample agent based on the Google [Agent Development Kit](https://google.github.io/adk-docs/) and [Gemini Flash 2.5](https://deepmind.google/models/gemini/flash/) -- best for interacting with a sample ADK-based web agent; requires some additional setup.

For other clients/agents, see the relevant documentation; you should be able to reuse the commands and arguments detailed below.

### Prerequisites

For all instances:

- A Data Commons API key. To obtain an API key, go to <https://apikeys.datacommons.org> and request a key for the `api.datacommons.org` domain.
- For running the sample agent or the Colab notebook or optionally, Gemini CLI, get a Gemini-enabled API key. To obtain a Gemini API key, go to <https://aistudio.google.com/app/apikey>.
- For Gemini CLI, running the sample agent locally, or running the server locally in standalone mode, install `uv` to install and manage Python packages; see the instructions at <https://github.com/astral-sh/uv/blob/main/README.md>. 
- For running the sample agent locally, install [Git](https://git-scm.com/).

> **Important**: Additionally, for custom Data Commons instances:

> If you have not rebuilt your Data Commons image since the stable release of 2025-09-08, you must [sync to the latest stable release](https://docs.datacommons.org/custom_dc/build_image.html#sync-code-to-the-stable-branch), [rebuild your image](https://docs.datacommons.org/custom_dc/build_image.html#build-package) and [redeploy](https://docs.datacommons.org/custom_dc/deploy_cloud.html#manage-your-service).

### Configure environment variables

#### Connecting to datacommons.org

For basic usage against datacommons.org, set the required `DC_API_KEY` in your shell/startup script (e.g. `.bashrc`).
```
export DC_API_KEY=<your API key>
```

#### Custom Data Commons

If you're running a against a custom Data Commons instance, we recommend using a `.env` file, which the server locates automatically, to keep all the settings in one place. All supported options are documented in https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/.env.sample. 

To set variables using a `.env` file:

1. From Github, download the file [`.env.sample`](https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/.env.sample) to the desired directory. Or, if you plan to run the sample agent, clone the repo https://github.com/datacommonsorg/agent-toolkit/.

1. From the directory where you saved the sample file, copy it to a new file called `.env`. For example:
   ```
   cd ~/agent-toolkit/packages/datacommons-mcp
   cp .env.sample .env
   ```
1. Set the following variables: 
   - `DC_API_KEY`: Set to your Data Commons API key
   - `DC_TYPE`: Set to `custom`.
   - `CUSTOM_DC_URL`: Uncomment and set to the URL of your instance. 
1. Optionally, set other variables.

### Use Gemini CLI

To install Gemini CLI, see instructions at https://github.com/google-gemini/gemini-cli#quick-install. 

We recommend that you use the [Gemini API key](https://github.com/google-gemini/gemini-cli?tab=readme-ov-file#option-2-gemini-api-key) or [Vertex API key](https://github.com/google-gemini/gemini-cli?tab=readme-ov-file#option-3-vertex-ai) authentication options if you already have a Google Cloud Platform project, so you don't have to log in for every session. 

To configure Gemini CLI to recognize the Data Commons server, edit your `~/.gemini/settings.json` file (or `settings.json` file in another directory) to add the following:

```json
{
  ...
  "selectedAuthType": "gemini-api-key",
  "mcpServers": {
    "datacommons-mcp": {
      "command": "uvx",
      "args": [
        "datacommons-mcp@latest",
        "serve",
        "stdio"
      ],
      "env": {
        "DC_API_KEY": "<your key>"
        "DC_API_KEY": "<your key>"
      }
    }
  }
}
```
If desired, you can modify the following settings:
- `selectedAuthType`: If you don't have a GCP project and want to use OAuth with your Google account, set this to `oauth-personal`.
- `command`: Set to `uv` if you want to run packages from locally stored Python code.

You can now run the `gemini` command from any directory and it will automatically kick off the MCP server, with the correct environment variables.

> Tip: If you run Gemini from the directory where your `.env` file is stored, you can omit the `env` section above.

Once Gemini CLI has started up, you can immediately begin sending natural-language queries! 

> **Tip**: To ensure that Gemini CLI uses the Data Commons MCP tools, and not its own `GoogleSearch` tool, include a prompt to use Data Commons in your query. For example, use a query like "Use Data Commons tools to answer the following: ..."  You can also add such a prompt to your [`GEMINI.md` file](https://codelabs.developers.google.com/gemini-cli-hands-on#9) so that it's persisted across sessions.

### Use the sample agent

xxx is a basic agent for interacting with the MCP Server. To run it locally:

1. Clone the Data Commons `agent-toolkit` repo: from the desired directory where you would like to save the code, run:
   ```
   git clone https://github.com/datacommonsorg/agent-toolkit.git
   ```
1. When the files are downloaded, navigate to the subdirectory `packages/datacommons_agents/`. For example:
   ```
   cd ~/agent-toolkit/packages/datacommons_agents/
   ```
1. Copy the `.env_sample` file to a new file `called `.env`:
   ```
   cp .env.sample .env
   ```
1. Set the required variables and save the file.
1. Run the following command to start the web agent and server:
   ```
   uv run adk web ./datacommons-agents
   ```
1. more coming...

## Develop your own ADK agent

We provide two sample Google Agent Development Kit-based agents you can use as inspiration for building your own agent:

- [Building an Agent with Data Commons Tools]() is a Google Colab tutorial that shows how to build an ADK Python agent step by step. 
- The sample [basic agent]() is a simple Python ADK agent you can use to develop locally. See [Use the sample agent](#use-the-sample-agent) above for details.

### Test with MCP Inspector

If you're interested in getting a deeper understanding of Data Commons tools and tool calls, the [MCP Inspector](https://modelcontextprotocol.io/legacy/tools/inspector) is a useful tool for interactively sending tool calls to the server. It runs locally and spawns a server. It uses token-based OAuth for authentication, which it generates itself, so you don't need to specify any keys.

To use it:

1. If not already installed on your system, install [`node.js`](https://nodejs.org/en/download) and [`uv`](https://github.com/astral-sh/uv/blob/main/README.md).
1. Ensure you've set up the relevant server [environment variables](#environment-variables). If you're using a `.env` file, go to the directory where the file is stored.
1. Run:
   ```
   npx @modelcontextprotocol/inspector uvx datacommons-mcp serve stdio
   ```
1. Open the Inspector via the pre-filled session token URL which is printed to terminal on server startup. It should look like `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=<session token>`. 
1. Click on the link to open the browser. The tool is prepopulated with all relevant variables.
1. In the left pane, click **Connect**. 

## Use a remote server/client

### Run a standalone server

1. Ensure you've set up the relevant server [environment variables](#environment-variables). If you're using a `.env` file, go to the directory where the file is stored.
1. Run:
   ```
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
...
"mcpServers": {
    "datacommons-mcp": {
      "httpUrl": "http://<host>:<port>/mcp"
    }
    ...
  }
}
```
#### Sample agent

To configure the sample agent xxx to connect to a remote Data Commons server over HTTP, replace the `mcpToolset` section in the agent initialization code in `packages/datacommons-agents/sample_agents/basic_agent/agent.py` with the following:

```python
    tools=[McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=f"http://<host>:<port>/mcp")
        )],
    ...
)
```





