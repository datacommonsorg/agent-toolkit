# DC MCP Server

A MCP server for fetching statistical data from Data Commons instances.

## Usage

See [Getting Started](https://github.com/datacommonsorg/agent-toolkit/tree/main?tab=readme-ov-file#getting-started) instructions.

### Configuration

The server uses configuration from [config.py](config.py) which supports:

- Base Data Commons instance
- Custom Data Commons instances
- Federation of multiple DC instances

Instantiate the clients in [server.py](server.py) based on the configuration.

```python
# Base DC client
multi_dc_client = create_clients(config.BASE_DC_CONFIG)

# Custom DC client
multi_dc_client = create_clients(config.CUSTOM_DC_CONFIG)

# Federation of multiple DC clients
multi_dc_client = create_clients(config.FEDERATED_DC_CONFIG)
```