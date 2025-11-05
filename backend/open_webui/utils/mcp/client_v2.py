"""
Enhanced MCP Client using native mcp.types

This module provides an enhanced MCP client that uses the native mcp.types
directly, reducing boilerplate while adding support for progress reporting
and rich content handling.
"""

import asyncio
from typing import Optional, Callable, Dict, Any
from contextlib import AsyncExitStack
import logging
from uuid import uuid4

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, Tool

from .content_utils import MCPToolResult, ProgressTracker

log = logging.getLogger(__name__)


class EnhancedMCPClient:
    """
    Enhanced MCP client with native type support and progress reporting

    This client uses mcp.types directly and provides utilities for working
    with rich content types and progress notifications.
    """

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self._progress_trackers: Dict[str, ProgressTracker] = {}
        self._progress_task: Optional[asyncio.Task] = None

    async def connect(self, url: str, headers: Optional[dict] = None):
        """Connect to MCP server"""
        try:
            self._streams_context = streamablehttp_client(url, headers=headers)

            transport = await self.exit_stack.enter_async_context(self._streams_context)
            read_stream, write_stream, _ = transport

            self._session_context = ClientSession(read_stream, write_stream)

            self.session = await self.exit_stack.enter_async_context(
                self._session_context
            )
            await self.session.initialize()

            # Start progress notification listener (if SDK supports it)
            self._start_progress_listener()

        except Exception as e:
            await self.disconnect()
            raise e

    def _start_progress_listener(self):
        """
        Start listening for progress notifications

        Note: The MCP Python SDK's notification handling is still evolving.
        This is a stub for when proper notification subscription is available.

        TODO: Once the SDK provides a way to subscribe to notifications,
        implement proper handling here. The expected flow:
        1. Subscribe to "notifications/progress"
        2. Match progressToken to active trackers
        3. Call the appropriate progress callback
        """
        # Placeholder for future implementation
        # When SDK supports it, this should:
        # self._progress_task = asyncio.create_task(self._handle_notifications())
        pass

    async def _handle_notifications(self):
        """
        Handle incoming notifications from the server

        This is a placeholder for proper notification handling.
        When the SDK supports notification streams, this should:
        1. Listen on the notification stream
        2. Filter for "notifications/progress"
        3. Update progress trackers
        4. Call progress callbacks
        """
        # Pseudocode for future implementation:
        """
        while self.session:
            try:
                # Wait for notification
                notification = await self.session.receive_notification()

                if notification.method == "notifications/progress":
                    params = notification.params
                    token = params.get("progressToken")

                    if token in self._progress_trackers:
                        tracker = self._progress_trackers[token]
                        update = tracker.update(
                            params.get("progress", 0),
                            params.get("total"),
                            params.get("message", "")
                        )

                        # Call the callback if set
                        if hasattr(tracker, 'callback') and tracker.callback:
                            await tracker.callback(update)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error handling notification: {e}")
        """
        pass

    async def list_tool_specs(self) -> Optional[list]:
        """
        List all available tools with their specs

        Returns tool specs including outputSchema if available
        """
        if not self.session:
            raise RuntimeError("MCP client is not connected.")

        result = await self.session.list_tools()
        tools: list[Tool] = result.tools

        tool_specs = []
        for tool in tools:
            spec = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            }

            # Include output schema if available
            if hasattr(tool, "outputSchema") and tool.outputSchema:
                spec["output_schema"] = tool.outputSchema

            tool_specs.append(spec)

        return tool_specs

    async def call_tool(
        self,
        function_name: str,
        function_args: dict,
        progress_callback: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> MCPToolResult:
        """
        Call a tool with progress support

        Args:
            function_name: Name of the tool to call
            function_args: Arguments to pass to the tool
            progress_callback: Optional callback for progress updates
                             Receives dict with: progress, total, percentage, message

        Returns:
            MCPToolResult wrapping the native CallToolResult
        """
        if not self.session:
            raise RuntimeError("MCP client is not connected.")

        # Generate progress token if callback provided
        progress_token = None
        if progress_callback:
            progress_token = str(uuid4())
            tracker = ProgressTracker(progress_token)
            tracker.callback = progress_callback  # Store callback on tracker
            self._progress_trackers[progress_token] = tracker

        # Prepare arguments with progress token if needed
        # Note: The MCP spec uses _meta for metadata like progressToken
        call_args = function_args.copy()
        if progress_token:
            # According to MCP spec, progressToken goes in meta/params
            # The exact structure may depend on SDK version
            if "_meta" not in call_args:
                call_args["_meta"] = {}
            call_args["_meta"]["progressToken"] = progress_token

        try:
            # Call the tool - this returns native CallToolResult
            result: CallToolResult = await self.session.call_tool(
                function_name, call_args
            )

            if not result:
                raise Exception("No result returned from MCP tool call.")

            # Wrap in our utility class
            mcp_result = MCPToolResult(result)

            # If it's an error, raise an exception
            if mcp_result.is_error:
                error_text = mcp_result.get_text_content()
                raise Exception(f"Tool error: {error_text}")

            return mcp_result

        finally:
            # Clean up progress tracker
            if progress_token and progress_token in self._progress_trackers:
                del self._progress_trackers[progress_token]

    async def call_tool_raw(
        self, function_name: str, function_args: dict
    ) -> CallToolResult:
        """
        Call a tool and return the raw CallToolResult

        This provides direct access to the native MCP type for advanced use cases.
        """
        if not self.session:
            raise RuntimeError("MCP client is not connected.")

        result: CallToolResult = await self.session.call_tool(
            function_name, function_args
        )

        if not result:
            raise Exception("No result returned from MCP tool call.")

        return result

    async def list_resources(self, cursor: Optional[str] = None) -> Optional[dict]:
        """List available resources"""
        if not self.session:
            raise RuntimeError("MCP client is not connected.")

        result = await self.session.list_resources(cursor=cursor)
        if not result:
            raise Exception("No result returned from MCP list_resources call.")

        result_dict = result.model_dump()
        resources = result_dict.get("resources", [])

        return resources

    async def read_resource(self, uri: str) -> Optional[dict]:
        """Read a resource"""
        if not self.session:
            raise RuntimeError("MCP client is not connected.")

        result = await self.session.read_resource(uri)
        if not result:
            raise Exception("No result returned from MCP read_resource call.")

        result_dict = result.model_dump()
        return result_dict

    async def disconnect(self):
        """Disconnect and clean up"""
        # Cancel progress listener
        if self._progress_task:
            self._progress_task.cancel()
            try:
                await self._progress_task
            except asyncio.CancelledError:
                pass

        # Clean up session
        await self.exit_stack.aclose()

    async def __aenter__(self):
        await self.exit_stack.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.exit_stack.__aexit__(exc_type, exc_value, traceback)
        await self.disconnect()


class MCPClient(EnhancedMCPClient):
    """
    Backward compatible MCP client

    This maintains the same interface as the original client.py
    but uses native types internally.
    """

    async def call_tool(
        self, function_name: str, function_args: dict
    ) -> Optional[dict]:
        """
        Call tool with backward compatible return format

        Returns a dict with content for compatibility with existing code.
        """
        # Call the enhanced version
        result = await super().call_tool(function_name, function_args)

        # Convert native CallToolResult to dict format for compatibility
        return result.result.model_dump(mode="json").get("content")
