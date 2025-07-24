# DC MCP Server

A MCP server for fetching statistical data from Data Commons instances.

## Usage


### Start MCP Server

Option 1: Use the datacommons-mcp cli
```bash
export DC_API_KEY={YOUR_API_KEY}
uv run datacommons-mcp serve (http|stdio)
```

Option 2: Use the fastmcp cli
To start the MCP server, run:
```bash
export DC_API_KEY={YOUR_API_KEY}
cd packages/datacommons-mcp # navigate to package dir
uv run fastmcp run datacommons_mcp/server.py:mcp -t (sse|stdio)
```


### Test with MCP Inspector

> IMPORTANT: Open the inspector via the **pre-filled session token url** which is printed to terminal on server startup.
> * It should look like `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN={session_token}`

Option 1: run inspector + datacommons-mcp cli
```bash
export DC_API_KEY=<your-key> 
npx @modelcontextprotocol/inspector uv run datacommons-mcp serve stdio
```

The following values should be automatically populated:

- Transport Type: `STDIO`
- Command: `uv`
- Arguments: `run datacommons-mcp serve stdio`


Option 2: fastmcp cli
```bash
export DC_API_KEY={YOUR_API_KEY}
cd packages/datacommons-mcp # navigate to package dir
uv run fastmcp dev datacommons_mcp/server.py
```

Make sure to use the MCP Inspector URL with the prefilled session token!

The connection arguments should be prefilled with:
* Transport Type = `STDIO`
* Command = `uv`
* Arguments = `run --with mcp mcp run datacommons_mcp/server.py`

### Configuration

The server uses configuration from [config.py](config.py) which supports:

- Base Data Commons instance only
- Base Data Commons instance + one custom Data Commons instance

Instantiate the clients in [server.py](server.py) based on the configuration.

```python
# Base DC client only
multi_dc_client = create_clients(config.BASE_DC_CONFIG)

# Base DC + one custom DC client
multi_dc_client = create_clients(config.CUSTOM_DC_CONFIG)
```


## Dev Notes

### File Checks + Formatting
```bash
uv run ruff check # to check files

uv run ruff format # to format files
```