# DataCommons MCP Extension for Claude Desktop

A Claude Desktop extension that provides access to the [Data Commons](https://datacommons.org/) Knowledge Graph through the Model Context Protocol (MCP).

## What is This?

This extension enables Claude to access statistical data from Data Commons, a Google-led initiative that provides open access to public datasets. With this extension, you can ask Claude questions about:

- Population statistics
- Economic indicators
- Health metrics
- Climate data
- Educational statistics
- And much more from thousands of datasets

## Quick Install

1. **Download** the extension: `datacommons-mcp.mcpb` (or [build from source](#building-from-source))

2. **Get a DataCommons API key**:
   - Visit https://datacommons.org/
   - Sign up for a free API key

3. **Install in Claude Desktop**:
   - Open Claude Desktop
   - Go to **Settings → Developer → Extensions**
   - Click **"Install from .mcpb file"**
   - Select `datacommons-mcp.mcpb`

4. **Configure your API key**:
   - In the Extensions settings, find **datacommons-mcp**
   - Click **"Configure"**
   - Enter your DataCommons API key in the **DC_API_KEY** field
   - Save the configuration

5. **Enable the extension** and restart Claude Desktop if needed

## Example Queries

Once installed, you can ask Claude:

- "What is the current population of California?"
- "Show me unemployment rates in the United States over the past 10 years"
- "What are the median income levels across different states?"
- "Compare life expectancy in different countries"
- "What are the carbon emission trends in major cities?"

## Available Tools

The extension provides these MCP tools to Claude:

- **`get_observations`** - Retrieve statistical observations for specific places, variables, and dates
- **`search_indicators`** - Search for statistical indicators and variables in the Data Commons graph

## Building from Source

See [EXTENSION-BUILD.md](./EXTENSION-BUILD.md) for detailed build instructions.

Quick build:
```bash
./build-extension.sh
```

This creates `datacommons-mcp.mcpb` (16MB) with all dependencies bundled.

## Troubleshooting

### Extension won't enable
- Check logs: `tail -f ~/Library/Logs/Claude/mcp*.log`
- Look for `[datacommons-mcp]` entries
- Verify your API key is configured in Claude Desktop settings

### "DC_API_KEY not configured" error
- Go to **Settings → Developer → Extensions**
- Find **datacommons-mcp** and click **"Configure"**
- Enter your DataCommons API key
- Save and restart Claude Desktop

### "Module not found" errors
- Rebuild the extension with `./build-extension.sh`
- Ensure you're using the built `.mcpb` file, not a manually packed one

### API errors
- Verify your API key at https://datacommons.org/
- Check that the key is entered correctly in Claude Desktop extension settings
- Ensure you have internet connectivity

### Where is the API key stored?
- Your API key is configured through Claude Desktop's extension settings
- No local config files are needed
- Each user configures their own API key when they enable the extension

## Technical Details

- **Package size**: 16.1MB
- **Python dependencies**: 63 packages bundled
- **MCP Protocol**: 2025-06-18
- **License**: Apache-2.0

### Architecture

The extension bundles:
- DataCommons MCP server (`datacommons_mcp/`)
- All Python dependencies in `lib/` directory
- Sets `PYTHONPATH` to find dependencies at runtime

## Links

- **Repository**: https://github.com/datacommonsorg/agent-toolkit
- **Data Commons**: https://datacommons.org/
- **MCP Specification**: https://modelcontextprotocol.io/
- **Issue Tracker**: https://github.com/datacommonsorg/agent-toolkit/issues

## License

Apache-2.0 - see [LICENSE](./LICENSE) file for details.
