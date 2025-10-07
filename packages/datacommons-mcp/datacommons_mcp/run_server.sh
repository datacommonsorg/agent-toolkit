#!/bin/bash
# Wrapper script to run MCP server with proper config handling

# Debug output
echo "============================================================" >&2
echo "MCP Server Wrapper (Shell)" >&2
echo "============================================================" >&2
echo "Arguments: $@" >&2
echo "Environment DC_API_KEY: ${DC_API_KEY:-<not set>}" >&2
echo "PWD: $PWD" >&2
echo "Script dir: $(dirname "$0")" >&2
echo "============================================================" >&2

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Check if API key is in environment
if [ -z "$DC_API_KEY" ]; then
    echo "⚠️  DC_API_KEY not in environment, checking for config file..." >&2

    # Try to find config file in various locations
    CONFIG_LOCATIONS=(
        "$SCRIPT_DIR/.env"
        "$SCRIPT_DIR/../.env"
        "$HOME/.datacommons/config"
    )

    for config_file in "${CONFIG_LOCATIONS[@]}"; do
        if [ -f "$config_file" ]; then
            echo "Found config file: $config_file" >&2
            # Source the file to load DC_API_KEY
            source "$config_file"
            if [ -n "$DC_API_KEY" ]; then
                echo "✓ Loaded DC_API_KEY from $config_file" >&2
                break
            fi
        fi
    done
fi

# Export it for the Python process
export DC_API_KEY

# Launch the Python server
exec python "$SCRIPT_DIR/run_server.py" "$@"
