# DC MCP Server

A MCP server for fetching statistical data from Data Commons instances.

## Development

### Start MCP locally

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
uv run fastmcp run datacommons_mcp/server.py:mcp -t (http|stdio)
```

### Run Unit Tests

Run unit tests and evals using pyest:

```
export DC_API_KEY={YOUR_API_KEY}
uv run pytest
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

### Unit Testing

This project uses `pytest` for unit testing.

#### One-Time Setup

For a smoother development experience, it's recommended to create a virtual environment and install the package in editable mode with its test dependencies. This allows your IDE to find the modules and provide features like autocompletion.

From the root of the `dc-agent-toolkit` repository:

```bash
# 1. Create a virtual environment in the repo root
uv venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Install the package in editable mode with test dependencies
uv pip install -e .[test]
```

Now your environment is ready for running tests.

#### Run tests on the command line

```bash
# If you followed the one-time setup and activated the venv:
pytest

# Alternatively, if you haven't installed test dependencies in your venv:
uv run --extra test pytest
```

#### Run and debug tests in VSCode:

To setup:
1. Select the Python Interpreter:
   * Open the Command Palette (Cmd+Shift+P on macOS, Ctrl+Shift+P on Windows/Linux).
   * Type "Python: Select Interpreter" and choose the one created by uv

1. Configure the Test Runner:
   * Open the Command Palette again.
   * Type Python: Configure Tests and select pytest.
      * When prompted, choose the `packages` directory.

1.  Run and Debug from the Test Explorer:
   * Open the Testing tab from the activity bar (it looks like a beaker).
      * Click the "Refresh Tests" button if your tests haven't appeared.
   * You can now run and debug tests! See [VSCode Testing documentation](https://code.visualstudio.com/docs/debugtest/testing#_run-and-debug-tests) for further instruction.


### DC client configuration

The server uses configuration from [config.py](config.py) which supports:

- Base Data Commons instance
- Custom Data Commons instance

Instantiate the clients in [server.py](server.py) based on the configuration.

> **TODO**: Configuration will soon be changed from hardcoded config in code to configuration via environment variables for better deployment flexibility.

```python
# Base DC client only
dc_client = create_dc_client(config.BASE_DC_CONFIG)

# Custom DC client (includes base + custom search capabilities)
dc_client = create_dc_client(config.CUSTOM_DC_CONFIG)
```

### File Checks + Formatting
```bash
uv run ruff check # to check files

uv run ruff format # to format files
```

## Publishing a New Version

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