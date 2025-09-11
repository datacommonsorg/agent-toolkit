# Introducing Data Commons MCP server

* TOC

## Overview

The Data Commons Model Context Protocol (MCP) Server gives AI agents access to the Data Commons knowledge graph and returns data related to statistical variables, topics, and observations. It allows end users to formulate complex natural-language queries interactively, get data in textual, structured or unstructured formats, and download the data as desired. For example, you can answer high-level questions such as "give me the economic indicators of the BRICS countries", view simple tables, and download a CSV file of the data in tabular format.

The MCP Server returns data from the "base" instance (in datacommons.org) or, if configured, a Custom Data Commons instance. 

The server is a Python binary based on the [FastMCP 2.0 framework](https://gofastmcp.com). It runs in a Python virtual environment. A prebuilt package is available at https://pypi.org/project/datacommons-mcp/.

At this time, there is no centrally deployed server; you run your own server, and any client you want to connect to it. Initially, only local usage is supported. 

![alt text](mcp.png)

> **Note: At this time the server is experimental and subject to change.**

### Clients

You can use any available AI application to connect to the Data Commons MCP Server, or your own custom agent. 

The server supports both standard MCP transport protocols:
- Stdio: For clients that connect directly using local processes
- Streamable HTTP: For clients that connect remotely or otherwise require HTTP (e.g. Typescript)

Below we provide specific instructions for locally running agents:
- [Gemini CLI](https://github.com/google-gemini/gemini-cli)
- A sample agent based on the Google [Agent Development Kit](https://google.github.io/adk-docs/) and Gemini Flash.

To build your own Data Commons MCP client, see ...

### Tools

The server currently supports the following tools:

- `search_indicators`: Searches for available variables and/or topics for a given place or metric. Topics are only relevant for custom Data Commons instances that have implemented them.
- `validate_child_place_types`: Validates child place types for a given parent place.
- `get_observations`: Fetches statistical data for a given variable and place.

### Unsupported features

At the current time, the following are not supported:
- Non-geographical ("custom") entities
- Events
- Exploring nodes and relationships in the graph

## Install and run the server locally

### Prerequisites

- Data Commons API key. To obtain an API key, go to <https://apikeys.datacommons.org> and request a key for the `api.datacommons.org` domain.
- Install `uv`, for installing and running Python packages; see the instructions at <https://github.com/astral-sh/uv/blob/main/README.md>. 
- Optional: If you want to clone the Github repository and run the code locally, install [Git](https://git-scm.com/).

### Configure environment variables

You configure the server using environment variables. For local development, you can set variables on the command line, but we recommend using a `.env` file to save the settings between sessions. To do so:

1. From Github, download the file [`.env.sample`](https://github.com/datacommonsorg/agent-toolkit/blob/main/packages/datacommons-mcp/.env.sample) to the desired directory. The file provides complete documentation on all available options.

    > Tip: If you regularly use Git and want to run packages from local code, clone the repo https://github.com/datacommonsorg/agent-toolkit/.

1. From the directory where you saved the sample file, copy it to a new file called `.env`. For example:
   ```
   cd agent-toolkit/packages/datacommons-mcp
   cp .env.sample .env
   ```
1. Set the required variable `DC_API_KEY` to your Data Commons API key, and any other optional variables. If you are using a Custom Data Commons instance, be sure to set `DC_TYPE` to `custom` and uncomment and set `CUSTOM_DC_URL` to the URL of your instance. 

### Start and connect to the server

Both Gemini CLI and the sample Data Commons agent automatically spawn a local MCP server when you run them.

If you're using a different agent and/or want to connect from a remote client, you can start up the server independently instead, as described in [Start the server in standalone mode](#standalone).

#### Use Gemini CLI

To install Gemini CLI, see instructions at https://github.com/google-gemini/gemini-cli#quick-install. 
We recommend that you use the Gemini API key [authentication option](https://github.com/google-gemini/gemini-cli?tab=readme-ov-file#-authentication-options) if you already have a Google Cloud Platform project, so you don't have to log in for every session. To do so, go to https://aistudio.google.com/ and create a key.

To configure Gemini CLI to recognize the Data Commons server, edit your `~/.gemini/settings.json` file.  Add the following configuration:

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
        "DC_API_KEY": "<YOUR API KEY>"
      }
    }
  }
}
```

If desired, you can modify the following settings:
- `selectedAuthType`: If you don't have a GCP project and want to use OAuth with your Google account, set to `oauth-personal`.
- `command`: Set to `uv` if you want to run packages from locally stored Python code.
- `args`: Set `stdio` to `http` if you want to use streaming HTTP as the transport protocol.

You can now run the `gemini` command from any directory and it will automatically kick off the MCP server, with the correct environment variables.

Once Gemini CLI has started up, you can immediately begin sending natural-language queries! 

#### Use the sample agent

xxx is a basic agent for interacting with the MCP Server.

TODO: Write this when a PyPi package is created. 

{: #standalone}
## Start the server in standalone mode

To install packages from PyPi:
1. Go to the directory where your `.env` file is stored (e.g. `agent-toolkit/packages/datacommons-mcp`).
1. Run the following command:
   ```
   uvx datacommons-mcp serve <PROTOCOL>
   ```
To install packages from local code (cloned from Github):
1. Go to the server project directory:
   ```
   cd agent-toolkit/packages/datacommons-mcp
   ```
1. Ensure a copy of your `.env` file is present in the directory.
1. Run the following command:
   ```
   uv run datacommons-mcp serve <PROTOCOL>
   ```
The _PROTOCOL_ is one of:
- `stdio`: suitable for most locally running clients
- `http`: suitable for remote clients or other clients that require HTTP. The server is addressable on port 8080, with the endpoint `mcp`. For example, to point a locally running client to the server, you can use http://localhost:8080/mcp.


