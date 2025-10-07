#!/bin/bash
# Setup script for DataCommons MCP extension config

echo "============================================================"
echo "DataCommons MCP Extension - Configuration Setup"
echo "============================================================"
echo

# Check if config directory exists
CONFIG_DIR="$HOME/.datacommons"
CONFIG_FILE="$CONFIG_DIR/config"

# Create directory if it doesn't exist
if [ ! -d "$CONFIG_DIR" ]; then
    echo "Creating config directory: $CONFIG_DIR"
    mkdir -p "$CONFIG_DIR"
fi

# Check if config file already exists
if [ -f "$CONFIG_FILE" ]; then
    echo "⚠️  Config file already exists: $CONFIG_FILE"
    echo
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
fi

# Prompt for API key
echo
echo "Please enter your DataCommons API key:"
echo "(Get yours at: https://datacommons.org/)"
echo
read -p "API Key: " API_KEY

if [ -z "$API_KEY" ]; then
    echo "✗ No API key provided. Setup cancelled."
    exit 1
fi

# Write config file
echo "DC_API_KEY=$API_KEY" > "$CONFIG_FILE"
chmod 600 "$CONFIG_FILE"  # Make it readable only by the user

echo
echo "✓ Configuration saved to: $CONFIG_FILE"
echo
echo "Next steps:"
echo "1. Restart Claude Desktop if it's running"
echo "2. Enable the datacommons-mcp extension"
echo "3. Try asking: 'What is the population of California?'"
echo
echo "============================================================"
