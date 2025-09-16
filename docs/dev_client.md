## Debug tool calls

[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) is a tool for inspecting and debugging MCP servers, using actual MCP tool calls. This tool is useful if you are building your own MCP client and want to test calls to the server.  You will need to have [`node.js`](https://nodejs.org/en/download) installed before you can use it.

To use it with the Data Commons MCP server:

1. Go to the directory where your `.env` file is stored (e.g. `agent-toolkit/packages/datacommons-mcp`).
1. Run the following command:

Once connected, you can use the inspector to test the `get_observations` tool. Try the following parameters to get started:

- variable_desc: `population`
- place_name: `usa`

You can start the MCP inspector on port 6277. Look at the output for the pre-filled proxy auth token URL.

```bash
DC_API_KEY=<your-key> npx @modelcontextprotocol/inspector uvx datacommons-mcp serve stdio
```

> IMPORTANT: Open the inspector via the **pre-filled session token url** which is printed to terminal on server startup.
> * It should look like `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN={session_token}`

Then to connect to this MCP server, enter the following values in the inspector UI:

- Transport Type: `STDIO`
- Command: `uvx`
- Arguments: `datacommons-mcp serve stdio`

Click `Connect`


### Test with MCP Inspector

You can start the MCP inspector on port 6277. Look at the output for the pre-filled proxy auth token URL.

# Using environment variable
DC_API_KEY=<your-key> npx @modelcontextprotocol/inspector uvx datacommons-mcp serve stdio

# Or using .env file
npx @modelcontextprotocol/inspector uvx datacommons-mcp serve stdio
IMPORTANT: Open the inspector via the pre-filled session token url which is printed to terminal on server startup.

It should look like http://localhost:6274/?MCP_PROXY_AUTH_TOKEN={session_token}
Then to connect to this MCP server, enter the following values in the inspector UI:

Transport Type: STDIO
Command: uvx
Arguments: datacommons-mcp serve stdio
Click Connect



