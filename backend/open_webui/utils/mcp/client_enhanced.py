"""
Enhanced MCP Client with full content type and progress support

This module provides an enhanced MCP client that:
- Parses all content types (text, image, audio, resources)
- Supports progress reporting via progressToken
- Handles structured content
- Provides rich metadata and annotations
"""

import asyncio
from typing import Optional, Callable, Dict, Any
from contextlib import AsyncExitStack
import logging
from uuid import uuid4

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .content_parser import MCPContentParser, MCPToolResult, ProgressTracker

log = logging.getLogger(__name__)


class EnhancedMCPClient:
    """
    Enhanced MCP client with full content type and progress support
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

            # Start progress notification listener
            self._progress_task = asyncio.create_task(
                self._listen_for_progress_notifications()
            )

        except Exception as e:
            await self.disconnect()
            raise e

    async def _listen_for_progress_notifications(self):
        """
        Listen for progress notifications from the server

        Note: This is a placeholder for proper implementation.
        The actual implementation would need to tap into the session's
        notification stream, which may require modifications to the
        MCP Python SDK or using the session's internal mechanisms.
        """
        # TODO: Implement proper progress notification listening
        # This would require:
        # 1. Access to session's notification stream
        # 2. Filtering for "notifications/progress" messages
        # 3. Calling the appropriate progress callback

        # Pseudocode:
        # while self.session:
        #     try:
        #         notification = await self.session.receive_notification()
        #         if notification.method == "notifications/progress":
        #             token = notification.params.get("progressToken")
        #             if token in self._progress_trackers:
        #                 tracker = self._progress_trackers[token]
        #                 tracker.update(
        #                     notification.params.get("progress", 0),
        #                     notification.params.get("total"),
        #                     notification.params.get("message", "")
        #                 )
        #     except Exception as e:
        #         log.error(f"Error receiving progress notification: {e}")
        pass

    async def list_tool_specs(self) -> Optional[list]:
        """
        List all available tools with their specs

        Returns tool specs including outputSchema if available
        """
        if not self.session:
            raise RuntimeError("MCP client is not connected.")

        result = await self.session.list_tools()
        tools = result.tools

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
                log.debug(f"Tool {tool.name} has output schema: {tool.outputSchema}")

            tool_specs.append(spec)

        return tool_specs

    async def call_tool(
        self,
        function_name: str,
        function_args: dict,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> MCPToolResult:
        """
        Call a tool with enhanced content parsing and progress support

        Args:
            function_name: Name of the tool to call
            function_args: Arguments to pass to the tool
            progress_callback: Optional callback for progress updates
                             Receives dict with: progress, total, percentage, message

        Returns:
            MCPToolResult with parsed content blocks, structured content, etc.
        """
        if not self.session:
            raise RuntimeError("MCP client is not connected.")

        # Generate progress token if callback provided
        progress_token = None
        if progress_callback:
            progress_token = str(uuid4())
            tracker = ProgressTracker(progress_token)
            self._progress_trackers[progress_token] = tracker

            # Wrap callback to use tracker
            original_callback = progress_callback

            async def wrapped_callback(progress_data):
                try:
                    await original_callback(progress_data)
                except Exception as e:
                    log.error(f"Error in progress callback: {e}")

            # Store wrapped callback
            tracker.callback = wrapped_callback

        # Add progress token to request metadata
        call_args = function_args.copy()
        if progress_token:
            # Use _meta field for progress token
            call_args["_meta"] = {"progressToken": progress_token}

        try:
            # Call the tool
            result = await self.session.call_tool(function_name, call_args)

            if not result:
                raise Exception("No result returned from MCP tool call.")

            # Convert to dict for parsing
            result_dict = result.model_dump(mode="json")

            # Parse the result with full content type support
            parsed_result = MCPContentParser.parse_tool_result(result_dict)

            # If it's an error, raise an exception
            if parsed_result.is_error:
                error_text = parsed_result.get_text_content()
                raise Exception(f"Tool error: {error_text}")

            return parsed_result

        finally:
            # Clean up progress tracker
            if progress_token and progress_token in self._progress_trackers:
                del self._progress_trackers[progress_token]

    async def call_tool_simple(
        self, function_name: str, function_args: dict
    ) -> Optional[dict]:
        """
        Call a tool with simple dict return (backward compatible)

        This maintains compatibility with existing code while still
        providing some enhanced parsing.
        """
        parsed_result = await self.call_tool(function_name, function_args)

        # Convert to simple dict format
        result_dict = {
            "text": parsed_result.get_text_content(),
            "structured": parsed_result.structured_content,
            "is_error": parsed_result.is_error,
        }

        # Add media references
        image_blocks = parsed_result.get_image_blocks()
        if image_blocks:
            result_dict["images"] = [
                {"mime_type": img.mime_type, "data": img.data}
                for img in image_blocks
            ]

        audio_blocks = parsed_result.get_audio_blocks()
        if audio_blocks:
            result_dict["audio"] = [
                {"mime_type": aud.mime_type, "data": aud.data}
                for aud in audio_blocks
            ]

        return result_dict

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


# Backward compatible wrapper
class MCPClient(EnhancedMCPClient):
    """
    Backward compatible MCP client that uses enhanced features
    but maintains the same interface
    """

    async def call_tool(
        self, function_name: str, function_args: dict
    ) -> Optional[dict]:
        """
        Call tool with backward compatible return format

        Returns plain dict with content for compatibility
        """
        return await self.call_tool_simple(function_name, function_args)
