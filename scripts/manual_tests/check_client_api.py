"""Check FastMCP Client API."""

import inspect

from fastmcp.client import Client

# Check call_tool signature
sig = inspect.signature(Client.call_tool)
print("Client.call_tool signature:")
print(f"  {sig}")
print("\nParameters:")
for name, param in sig.parameters.items():
    print(f"  {name}: {param.annotation}, default={param.default}")
