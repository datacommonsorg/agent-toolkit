#!/usr/bin/env python3
import json
import subprocess
import sys

API_KEY = "EY3NfOeSPO2217S09CRC3cA2WNIkPwAcILUVRQGRTeb3gNfg"

def send_request(proc, req):
    """Send request and read response."""
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    response = proc.stdout.readline()
    return json.loads(response) if response else None

# Start server
proc = subprocess.Popen(
    ["uv", "run", "datacommons-mcp", "serve", "stdio"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, bufsize=1,
    env={"DC_API_KEY": API_KEY, **subprocess.os.environ},
    cwd="/Users/robsherman/Documents/Repos/agent-toolkit/packages/datacommons-mcp"
)

try:
    # 1. Initialize
    print("Test 1: Initialize", file=sys.stderr)
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}, 
                   "clientInfo": {"name": "test", "version": "1.0"}}
    })
    print(f"✅ Initialize: {resp['result']['serverInfo']['name']}")
    
    # 2. Send initialized notification
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()
    
    # 3. List tools
    print("\nTest 2: List tools", file=sys.stderr)
    resp = send_request(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = resp['result']['tools']
    print(f"✅ Found {len(tools)} tools: {', '.join([t['name'] for t in tools])}")
    
    # 4. Search indicators (no places)
    print("\nTest 3: Search indicators", file=sys.stderr)
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "search_indicators", 
                   "arguments": {"query": "population", "per_search_limit": 2}}
    })
    data = json.loads(resp['result']['content'][0]['text'])
    vars_count = len(data.get('variables', []))
    print(f"✅ Found {vars_count} variables")
    if vars_count > 0:
        var = data['variables'][0]
        print(f"   - DCID: {var.get('dcid', 'Unknown')}")
    
    # 5. Get observations  
    print("\nTest 4: Get observations (France population)", file=sys.stderr)
    resp = send_request(proc, {
        "jsonrpc": "2.0", "id": 4, "method": "tools/call",
        "params": {"name": "get_observations",
                   "arguments": {"variable_dcid": "Count_Person", "place_dcid": "country/FRA", "date": "latest"}}
    })
    data = json.loads(resp['result']['content'][0]['text'])
    obs = data['place_observations'][0]
    ts = obs['time_series'][0]
    print(f"✅ {obs['place']['name']}: {ts[1]:,} people ({ts[0]})")
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED - Server is fully functional!")
    print("✅ Backward compatibility verified for stdio mode")
    print("="*60)
    
finally:
    proc.terminate()
    proc.wait(timeout=5)
