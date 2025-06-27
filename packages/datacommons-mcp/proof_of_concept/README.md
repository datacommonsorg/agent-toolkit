# DC MCP Server

A MCP server for fetching statistical data from Data Commons instances.

## Usage

### Installation

1. Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set environment variables:

Copy the `.env.sample` file to `.env` and fill in your values.
```

### Running the Server

Start the server:

```bash
python server.py
```

The server will run on `http://localhost:8080` by default.

### Using MCP Inspector

[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is a tool for inspecting and debugging MCP servers.

There are many ways to install and run the inspector. The easiest is to run directly using `npx`:

```bash
npx @modelcontextprotocol/inspector
```

This will start the inspector on `http://localhost:6274` by default. 

> IMPORTANT: Open the inspector via the **pre-filled session token url** which is printed to terminal on server startup.
* It should look like `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN={session_token}`

Then to connect to this MCP server, enter the following values in the inspector UI:

- Transport Type: `SSE`
- URL: `http://localhost:8080/sse`

### Configuration

The server uses configuration from [config.py](config.py) which supports:

- Base Data Commons instance
- Custom Data Commons instances
- Federation of multiple DC instances

Instantiate the clients in [server.py](server.py) based on the configuration.

```python
# Base DC client
multi_dc_client = create_clients(config.BASE_DC_CONFIG)

# Custom DC client
multi_dc_client = create_clients(config.CUSTOM_DC_CONFIG)

# Federation of multiple DC clients
multi_dc_client = create_clients(config.FEDERATED_DC_CONFIG)
```