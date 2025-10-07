#!/usr/bin/env python3
"""
Wrapper script to run the MCP server with config handling.
"""

import os
import sys


def main() -> None:
    # Debug: Print all available info
    print("=" * 60, file=sys.stderr)
    print("MCP Server Startup Debug Info", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Check environment variables
    print("\nEnvironment Variables:", file=sys.stderr)
    for key in sorted(os.environ.keys()):
        if not key.startswith("_"):
            value = os.environ[key]
            if "KEY" in key or "TOKEN" in key or "SECRET" in key or "PASSWORD" in key:
                print(f"  {key}=<present, {len(value)} chars>", file=sys.stderr)
            else:
                print(f"  {key}={value[:80]}", file=sys.stderr)

    # Check command line arguments
    print(f"\nCommand Line Args: {sys.argv}", file=sys.stderr)

    # Look for DC_API_KEY in environment
    api_key_raw = os.environ.get("DC_API_KEY", "")
    api_key = api_key_raw.strip()  # Strip whitespace!

    print(
        f"\nInitial DC_API_KEY value: {api_key if not api_key else f'<{len(api_key)} chars>'}",
        file=sys.stderr,
    )
    if api_key_raw != api_key:
        print(
            f"  ⚠️  Stripped whitespace from API key (was {len(api_key_raw)} chars, now {len(api_key)} chars)",
            file=sys.stderr,
        )

    # Check if it's a placeholder that wasn't substituted
    if api_key and api_key.startswith("$"):
        print(
            f"⚠️  DC_API_KEY looks like an unsubstituted variable: {api_key}",
            file=sys.stderr,
        )
        api_key = ""  # Treat as not set

    # If no valid API key found, we need to fail gracefully
    if not api_key:
        print("\n" + "=" * 60, file=sys.stderr)
        print("❌ DC_API_KEY not configured", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(
            "\nPlease configure your DataCommons API key in Claude Desktop:",
            file=sys.stderr,
        )
        print("1. Go to Settings → Developer → Extensions", file=sys.stderr)
        print("2. Find the 'datacommons-mcp' extension", file=sys.stderr)
        print("3. Click 'Configure' and enter your API key", file=sys.stderr)
        print("4. Get your API key at: https://datacommons.org/", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        # Don't exit - let the server start so it can report the error properly
    else:
        # Explicitly set/export the DC_API_KEY environment variable (cleaned)
        os.environ["DC_API_KEY"] = api_key
        print(f"\n✓ DC_API_KEY configured ({len(api_key)} chars)", file=sys.stderr)

    print("=" * 60, file=sys.stderr)

    # Import the server module
    from datacommons_mcp.server import mcp

    # Run the FastMCP server
    print("Starting FastMCP server...", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
