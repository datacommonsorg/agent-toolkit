
# Data Commons Test Agents

This directory contains a collection of test agents built using the [Google Agent Development Kit (ADK)](https://github.com/google/agent-development-kit). These agents demonstrate how to interact with the Data Commons API to perform various tasks.

## Prerequisites

Before running the agents, you need to have a Data Commons API key. You can obtain one from the [Data Commons website](https://datacommons.org/api/key).

Once you have your API key, set it as an environment variable:

```bash
export DC_API_KEY=<your key>
```

## Getting Started

You can run the agents from the command line in two ways:

1. **Using the ADK web runner:**

   ```bash
   uv run adk web ./packages/datacommons-test-agents/
   ```

2. **Running the agent directly:**

   ```bash
   uv run adk run ./packages/datacommons-test-agents/datacommons_test_agents/basic_agent
   ```

## Evaluating Agents

To run the agent evaluations, use pytest:

```bash
uv run pytest
```

**Note:** You must have your `DC_API_KEY` environment variable set to run the evaluations, just as you do for running the agents.

## Development

You can use these test agents as a starting point for building your own custom agents. Simply copy one of the existing agents and modify it to suit your needs.

## License

This project is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file for details.
