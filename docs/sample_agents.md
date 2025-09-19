# Data Commons Sample Agents

Location: [packages/datacommons-mcp/examples/sample_agents](packages/datacommons-mcp/examples/sample_agents)

Reference [Google Agent Development Kit (ADK)](https://github.com/google/adk-python) agents demonstrating interaction with Data Commons via MCP.

## Agents

- **`basic_agent`**: Minimal agent demonstrating MCP-based interaction.


## Prerequisites

Export the following environment variables:

1.  `DC_API_KEY`: Your Data Commons API key. ([Get one](https://datacommons.org/api/key)).
2.  `GEMINI_API_KEY`: Your Gemini API key. ([Setup instructions](https://google.github.io/adk-docs/get-started/quickstart/#env)).

```bash
export DC_API_KEY="<your-dc-key>"
export GEMINI_API_KEY="<your-gemini-key>"
```

## Usage

All commands must be run from the repository root.

1.  ADK Web Runner

Serves all agents in the directory via the ADK web UI.

```bash
uvx --from google-adk adk web ./packages/datacommons-mcp/examples/sample_agents/
```

2.  ADK CLI Runner

Runs a single agent directly from the command line.

```bash
uvx --from google-adk adk run ./packages/datacommons-mcp/examples/sample_agents/basic_agent
```
