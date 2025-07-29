# Data Commons MCP Server

This is an experimental MCP server for fetching public information from [Data Commons](https://datacommons.org/).

**This is experimental and subject to change.**

## Requirements

1.  A Data Commons API key. You can get one from [apikeys.datacommons.org](https://apikeys.datacommons.org/).
2.  `uv`. You can find installation instructions at [https://astral.sh/uv](https://astral.sh/uv).

## Getting Started

Run the server with `uvx`:

**stdio**

```bash
DC_API_KEY=<your-key> uvx datacommons-mcp serve stdio
```

**http**

This will run the server with SSE on port 8080. You can access it at `http://localhost:8080/sse`.

```bash
DC_API_KEY=<your-key> uvx datacommons-mcp serve http
```

**Debugging**

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
      }
    }
  }
}
```

## Development

### Publishing a New Version

To publish a new version of `datacommons-mcp` to [PyPI](https://pypi.org/project/datacommons-mcp):

1. **Update the version**: Edit `packages/datacommons-mcp/datacommons_mcp/version.py` and increment the version number:
   ```python
   __version__ = "0.1.3"  # or whatever the new version should be
   ```

2. **Automatic publishing**: When your PR is merged to the main branch, the [GitHub Actions workflow](.github/workflows/build-and-publish-datacommons-mcp.yaml) will:
   - Detect the version bump
   - Build the package
   - Publish to PyPI at [https://pypi.org/project/datacommons-mcp](https://pypi.org/project/datacommons-mcp)
   - Create a git tag for the release

The package will be automatically available on PyPI after the workflow completes successfully. You can monitor the workflow progress at [https://github.com/datacommonsorg/agent-toolkit/actions](https://github.com/datacommonsorg/agent-toolkit/actions).
