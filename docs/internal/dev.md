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

The server uses configuration from environment variables or a `.env` file. 

- See [.env.sample](../.env.sample) for frequently used parameters and example configuration
- See [data_models/settings.py](../datacommons_mcp/data_models/settings.py) for all available configuration parameters

Create a `.env` file in the project root with your configuration.

### File Checks + Formatting
```bash
uv run ruff check # to check files

uv run ruff format # to format files
```

#### VS Code Integration
Install the [Ruff VS Code extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) to get:
- Automatic formatting on save
- Inline error highlighting and suggestions
- Real-time linting as you type


#### Pre Push Hook
To install a pre push hook for auto formatting and pytesting, run:
```bash
uv sync && uv run pre-commit install --hook-type pre-push # Configures pre-commit hooks for formatting repo prior to push
```
Note, this command must be re-run every time `.pre-commit-config.yaml` is updated.

To bypass the pre-push hooks and push to branch, use the --no-verify flag. For example:
```bash
git push origin $BRANCH --no-verify
```


## Releasing to PyPI <a name="release"></a>

### Versioning guidiance <a name="release-versioning"></a>

Use the following guidance for selecting the new version number (MAJOR.MINOR.PATCH):
*   Increment the **patch** version (third number) for minor fixes or internal implementation details that don't impact agentic clients.
*   Increment the **minor** version (second number) for changes to tool descriptions, minor changes to tool output structure, or larger internal implementation changes. These changes would be visible to the agentic client but likely not have a major impact.
*   Increment the **major** version (first number) for changes to the toolset offering, such as deleting, adding, or significantly changing a tool's "contract" with the agentic client.
      * **IMPORTANT**: Major version changes require follow-up updates to the Gemini CLI extension. See [How version affects the Gemini CLI extension](#gcli-extension) for details.

#### Pre Release Versioning
**For pre-releases**, you can append `rcN` (e.g., `0.2.0rc1`) to the version number, where `N` is an incrementing number starting from 1. These release candidates will be published to PyPI but are not automatically installed by tools like `pip` or `uv` unless explicitly specified, allowing for testing before a final release. 

   * **Note on RC Versioning:** Always base your release candidate number on the upcoming stable version. For example, the first RC for the 1.3.0 release should be 1.3.0rc1. This ensures that package managers like uv and pip will correctly treat 1.3.0 as the final, newer version once it's published. 

#### How version affects the Gemini CLI extension <a name="gcli-extension"></a>

The `datacommons` Gemini CLI extension locks to a specific `datacommons-mcp` version. This strategy avoids `uv` caching issues and makes it clear which MCP version is running for a given extension version, simplifying debugging and maintenance.

Therefore, when releasing a new stable version of the MCP server, you will likely need to release a new version of the extension as well.

This involves updating the locked `datacommons-mcp` version and the extension's version in its configuration, and then publishing a new extension release. If the MCP release includes major changes, you will also need to update the extension's context file ([`DATACOMMONS.md`](https://github.com/gemini-cli-extensions/datacommons/blob/main/DATACOMMONS.md)) with new tool orchestration instructions. More details on releasing the extension are in the internal Data Commons team docs.  

### Steps to publish a new version

To publish a new version of `datacommons-mcp` to [PyPI](https://pypi.org/project/datacommons-mcp):

1. **Update the version**: Edit `packages/datacommons-mcp/datacommons_mcp/version.py` and increment the version number:
   ```python
   __version__ = "x.y.z"  # see "Versioning guidance" above 
   ```

   * **Reminder**: If you are incrementing the major version, see [How version affects the Gemini CLI extension](#gcli-extension).

2. **Automatic publishing**: When your PR is merged to the main branch, the [GitHub Actions workflow](.github/workflows/build-and-publish-datacommons-mcp.yaml) will:
   - Detect the version bump
   - Build the package
   - Publish to PyPI at [https://pypi.org/project/datacommons-mcp](https://pypi.org/project/datacommons-mcp)
   - Create a git tag for the release

The package will be automatically available on PyPI after the workflow completes successfully. You can monitor the workflow progress at [https://github.com/datacommonsorg/agent-toolkit/actions](https://github.com/datacommonsorg/agent-toolkit/actions).

3. **Release the Gemini Extension**: After a new, stable `datacommons-mcp` version is published, release a new version of the `datacommons` Gemini CLI extension. Follow the instructions in the internal team docs to update the locked `datacommons-mcp` version and the extension's version, and then publish the extension.  
