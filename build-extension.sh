#!/bin/bash
set -e

echo "Building DataCommons MCP extension..."

# Clean previous builds
rm -rf build/ 2>/dev/null || true
rm -f datacommons-mcp.mcpb 2>/dev/null || true
rm -f agent-toolkit.mcpb 2>/dev/null || true

# Create build directory structure
mkdir -p build

# Copy the source code (just the datacommons_mcp package)
cp -r packages/datacommons-mcp/datacommons_mcp build/

# Create a lib directory for dependencies
mkdir -p build/lib

# Install dependencies into the lib directory using uv
echo "Installing Python dependencies..."
uv pip install \
  --target build/lib \
  --python /usr/local/bin/python \
  fastmcp requests datacommons-client pydantic pydantic-settings python-dateutil mcp httpx starlette anyio sse-starlette

# Copy manifest to build directory
cp manifest.json build/

# Pack from the root directory
mcpb pack build/

# Rename the output file
mv build.mcpb datacommons-mcp.mcpb

echo "✓ Extension built successfully: datacommons-mcp.mcpb"
echo "  Package size: $(du -h datacommons-mcp.mcpb | cut -f1)"
echo ""
echo "Install in Claude Desktop:"
echo "  Settings → Developer → Extensions → Install from .mcpb file"
echo "  Select: datacommons-mcp.mcpb"
