"""
MCP Client - Now using native mcp.types

This module now uses the enhanced implementation with native mcp.types
while maintaining backward compatibility with existing code.
"""

# Import the enhanced client that uses native types
from .client_v2 import MCPClient as EnhancedMCPClient, EnhancedMCPClient as _EnhancedBase

# Export the backward-compatible client
# This maintains the same interface as before but uses native types internally
class MCPClient(_EnhancedBase):
    """
    MCP Client with native type support

    This client now uses native mcp.types (TextContent, ImageContent, etc.)
    internally while maintaining backward compatibility with existing code.

    The call_tool() method returns the same dict format as before, but
    internally uses the enhanced implementation with:
    - Native mcp.types (TextContent, ImageContent, AudioContent)
    - Progress token support (prepared for SDK updates)
    - Better type safety with Pydantic models
    - Output schema support

    For advanced usage with full native type access, use EnhancedMCPClient directly.
    """
    pass


__all__ = ['MCPClient', 'EnhancedMCPClient']
