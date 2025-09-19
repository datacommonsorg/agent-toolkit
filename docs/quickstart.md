# Quickstart: Use Data Commons Tools with Gemini CLI

This page shows you how query datacommons.org using Gemini CLI. 

If you are using a custom Data Commons instance, please see the [User Guide](user_guide.md#custom-data-commons) for configuration instructions.

## Prerequisites

- A free Data Commons API key. To obtain an API key, go to <https://apikeys.datacommons.org> and request a key for the `api.datacommons.org` domain.
- Install `uv`, a tool for managing and installing Python packages: install from <https://docs.astral.sh/uv/getting-started/installation/>.
- Optional but recommended: If you have a Google Cloud Project, get a (free) Gemini-enabled API key from <https://aistudio.google.com/app/apikey>, and set the following environment variable in your shell/startup script:
   ```bash
   export GEMINI_API_KEY="<your key>"
   ```

## Install and configure Gemini CLI

1. Install Gemini CLI: see instructions at https://github.com/google-gemini/gemini-cli#quick-install. 
2. To configure Gemini CLI to recognize the Data Commons server, edit your `~/.gemini/settings.json` file (or `settings.json` file in another directory) to add the following:

```json
{
...
    "mcpServers": {
       "datacommons-mcp": {
           "command": "uvx",
            "args": [
                "datacommons-mcp@latest",
                "serve",
                "stdio"
            ],
            "env": {
                "DC_API_KEY": "<your Data Commons API key>"
            },
            "trust": true
        }
    }
...
}
```

If you are using your Google Account credentials (with OAuth), you are prompted to log in.

> Tip: If you are using a Gemini API key, you can also edit the settings file to include the authentication method above the `mcpServers` section:

```json
"selectedAuthType": "GEMINI_API_KEY",
```

## Query Data Commons

From any directory, run `gemini`. Once Gemini CLI has started up, you can immediately begin sending natural-language queries! 

To see the Data Commons tools, use `/mcp tools`.

> **Tip**: To ensure that Gemini CLI uses the Data Commons MCP tools, and not its own `GoogleSearch` tool, include a prompt to use Data Commons in your query. For example, use a query like "Use Data Commons tools to answer the following: ..."  You can also add such a prompt to your [`GEMINI.md` file](https://codelabs.developers.google.com/gemini-cli-hands-on#9) so that it's persisted across sessions.
