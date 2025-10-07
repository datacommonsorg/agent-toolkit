# Building the DataCommons MCP Extension

## Problem

When creating a `.mcpb` extension using `mcpb pack`, Python dependencies are not automatically bundled. This causes `ModuleNotFoundError` when the extension tries to run in Claude Desktop.

## Solution

The `build-extension.sh` script handles dependency bundling automatically:

1. Creates a `build/` directory structure
2. Copies the DataCommons MCP source code to `build/datacommons_mcp/`
3. Installs all Python dependencies into `build/lib/` using `uv`
4. Bundles everything into a single `.mcpb` file
5. The `manifest.json` sets `PYTHONPATH` to point to the bundled `lib/` directory

## Building the Extension

```bash
./build-extension.sh
```

This will create `datacommons-mcp.mcpb` (16MB) in the project root.

## Installing in Claude Desktop

1. Open Claude Desktop
2. Go to Settings → Developer → Extensions
3. Click "Install from .mcpb file"
4. Select `datacommons-mcp.mcpb`
5. Enable the extension and provide your DataCommons API key

Get your API key at: https://datacommons.org/

## Architecture

The packaged extension has this structure when installed:

```
Claude Extensions/local.mcpb.datacommons.datacommons-mcp/
├── lib/                          # Python dependencies (via PYTHONPATH)
│   ├── fastmcp/
│   ├── pydantic/
│   ├── requests/
│   ├── datacommons-client/
│   └── ... (63 total packages)
├── datacommons_mcp/              # Main package
│   ├── server.py                 # Entry point
│   ├── clients.py
│   ├── services.py
│   ├── topics.py
│   ├── data/                     # Topic cache data
│   └── data_models/              # Pydantic models
└── manifest.json
```

## Manifest Configuration

Key parts of `manifest.json`:

```json
{
  "name": "datacommons-mcp",
  "description": "Tools and agents for interacting with the Data Commons Knowledge Graph using the Model Context Protocol (MCP).",
  "server": {
    "type": "python",
    "entry_point": "datacommons_mcp/server.py",
    "mcp_config": {
      "command": "python",
      "args": [
        "${__dirname}/datacommons_mcp/server.py"
      ],
      "env": {
        "PYTHONPATH": "${__dirname}/lib"
      }
    }
  },
  "user_config": {
    "DC_API_KEY": {
      "type": "string",
      "title": "DataCommons API Key",
      "description": "API key for accessing Data Commons. Get yours at https://datacommons.org/",
      "required": true,
      "sensitive": true
    }
  }
}
```

The `${__dirname}` variable expands to the extension installation directory, and `PYTHONPATH` ensures Python can find the bundled dependencies.

## Dependencies

All dependencies from `packages/datacommons-mcp/pyproject.toml` are bundled:

- `fastmcp` - MCP framework
- `requests` - HTTP client
- `datacommons-client` - DataCommons API client
- `pydantic` - Data validation
- `python-dateutil` - Date parsing
- And all transitive dependencies

## Available Tools

The extension provides these MCP tools:

- **get_observations** - Get statistical observations from Data Commons
- **search_indicators** - Search for statistical indicators and variables

## Troubleshooting

### Check Extension Logs

```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

Look for the `[datacommons-mcp]` prefix in logs.

### Common Issues

1. **Missing dependencies**: Rebuild with `./build-extension.sh`
2. **Python version mismatch**: Extension uses system Python at `/usr/local/bin/python`
3. **Import errors**: Check that `PYTHONPATH` in manifest points to `${__dirname}/lib`
4. **ModuleNotFoundError**: Dependencies not bundled - rebuild extension
5. **API key errors**: Ensure you've configured your DataCommons API key in extension settings

## Development Workflow

1. Make changes to source code in `packages/datacommons-mcp/datacommons_mcp/`
2. Run `./build-extension.sh` to rebuild
3. In Claude Desktop:
   - Disable the extension
   - Reinstall the new `datacommons-mcp.mcpb` file
   - Re-enable and check logs
4. Test with a query like: "What is the population of California?"

## Package Contents

- **16.1MB** total size
- **63 Python packages** bundled
- **2,988 files** in the archive
- Main dependencies:
  - `fastmcp` 2.12.4 - MCP framework
  - `datacommons-client` 2.1.1 - API client
  - `pydantic` 2.11.10 - Data validation
  - `requests` 2.32.5 - HTTP client
