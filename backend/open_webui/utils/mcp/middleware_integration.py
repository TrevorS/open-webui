"""
MCP Middleware Integration

This module provides integration functions for processing MCP tool results
in the Open WebUI middleware, handling all content types and emitting
appropriate events for the frontend.
"""

import logging
import base64
from typing import Any, Dict, List, Optional, Tuple, Callable
from uuid import uuid4
import json

from .content_parser import (
    MCPToolResult,
    TextContentBlock,
    ImageContentBlock,
    AudioContentBlock,
    EmbeddedResourceBlock
)

log = logging.getLogger(__name__)


async def process_mcp_tool_result(
    request,
    tool_function_name: str,
    mcp_result: MCPToolResult,
    event_emitter: Optional[Callable] = None,
    metadata: Optional[Dict[str, Any]] = None,
    user=None,
) -> Tuple[str, List[Dict], List[str]]:
    """
    Process an MCP tool result with full content type support

    Args:
        request: FastAPI request object
        tool_function_name: Name of the tool that was called
        mcp_result: Parsed MCPToolResult
        event_emitter: Event emitter for sending events to frontend
        metadata: Request metadata
        user: User object

    Returns:
        Tuple of (tool_result_text, tool_result_files, tool_result_embeds)
    """
    tool_result_files = []
    tool_result_embeds = []
    tool_result_text_parts = []

    # Process each content block
    for block in mcp_result.content_blocks:
        if isinstance(block, TextContentBlock):
            # Add text to result
            tool_result_text_parts.append(block.text)

        elif isinstance(block, ImageContentBlock):
            # Process image
            try:
                image_file = await _process_image_content(
                    request, block, metadata, user, event_emitter
                )
                if image_file:
                    tool_result_files.append(image_file)
                    tool_result_text_parts.append(
                        f"[Generated Image: {image_file.get('name', 'image')}]"
                    )
            except Exception as e:
                log.error(f"Failed to process image content: {e}")
                tool_result_text_parts.append(f"[Image processing error: {str(e)}]")

        elif isinstance(block, AudioContentBlock):
            # Process audio
            try:
                audio_file = await _process_audio_content(
                    request, block, metadata, user, event_emitter
                )
                if audio_file:
                    tool_result_files.append(audio_file)
                    tool_result_text_parts.append(
                        f"[Generated Audio: {audio_file.get('name', 'audio')}]"
                    )
            except Exception as e:
                log.error(f"Failed to process audio content: {e}")
                tool_result_text_parts.append(f"[Audio processing error: {str(e)}]")

        elif isinstance(block, EmbeddedResourceBlock):
            # Process embedded resource
            if block.is_text_resource():
                tool_result_text_parts.append(
                    f"[Resource: {block.uri}]\n{block.text}"
                )
            else:
                # Binary resource - could be processed similar to image/audio
                tool_result_text_parts.append(
                    f"[Resource: {block.uri} ({block.mime_type})]"
                )

    # Emit files event if we have files
    if tool_result_files and event_emitter:
        try:
            await event_emitter({
                "type": "files",
                "data": {
                    "files": tool_result_files,
                    "tool": tool_function_name
                },
            })
        except Exception as e:
            log.error(f"Failed to emit files event: {e}")

    # Combine text parts
    tool_result_text = "\n".join(tool_result_text_parts)

    # If we have structured content, add it to the result
    if mcp_result.structured_content:
        try:
            structured_json = json.dumps(
                mcp_result.structured_content, indent=2, ensure_ascii=False
            )
            tool_result_text += f"\n\n[Structured Data]\n{structured_json}"
        except Exception as e:
            log.error(f"Failed to serialize structured content: {e}")

    return tool_result_text, tool_result_files, tool_result_embeds


async def _process_image_content(
    request,
    image_block: ImageContentBlock,
    metadata: Optional[Dict],
    user,
    event_emitter: Optional[Callable] = None
) -> Optional[Dict[str, Any]]:
    """
    Process an image content block and upload it

    Returns a file dict suitable for tool_result_files
    """
    try:
        from open_webui.routers.images import upload_image
        from io import BytesIO

        # Decode base64 image data
        image_data = image_block.decode_data()
        if not image_data:
            return None

        # Upload the image
        image_url = upload_image(
            request,
            BytesIO(image_data),
            image_block.mime_type,
            metadata or {},
            user
        )

        if not image_url:
            return None

        # Create file entry
        file_entry = {
            "type": "image",
            "name": f"mcp_image_{uuid4().hex[:8]}.{image_block.get_file_extension()}",
            "url": image_url,
            "mime_type": image_block.mime_type,
            "annotations": image_block.annotations,
        }

        return file_entry

    except Exception as e:
        log.error(f"Failed to process image content: {e}")
        return None


async def _process_audio_content(
    request,
    audio_block: AudioContentBlock,
    metadata: Optional[Dict],
    user,
    event_emitter: Optional[Callable] = None
) -> Optional[Dict[str, Any]]:
    """
    Process an audio content block and upload it

    Returns a file dict suitable for tool_result_files
    """
    try:
        from open_webui.routers.files import upload_file_handler
        from fastapi import UploadFile
        from io import BytesIO

        # Decode base64 audio data
        audio_data = audio_block.decode_data()
        if not audio_data:
            return None

        # Create an UploadFile-like object
        filename = f"mcp_audio_{uuid4().hex[:8]}.{audio_block.get_file_extension()}"

        # Upload the audio file
        # Note: This is a simplified approach - you may need to adapt
        # based on how your file upload system works

        file_entry = {
            "type": "audio",
            "name": filename,
            "data": audio_block.data,  # Keep base64 for now
            "mime_type": audio_block.mime_type,
            "annotations": audio_block.annotations,
        }

        return file_entry

    except Exception as e:
        log.error(f"Failed to process audio content: {e}")
        return None


async def create_mcp_progress_callback(
    event_emitter: Optional[Callable],
    tool_name: str
) -> Callable:
    """
    Create a progress callback that emits progress events

    Args:
        event_emitter: Event emitter function
        tool_name: Name of the tool for progress tracking

    Returns:
        Async callback function for progress updates
    """
    async def on_progress(progress_data: Dict[str, Any]):
        if event_emitter:
            try:
                await event_emitter({
                    "type": "tool_progress",
                    "data": {
                        "tool": tool_name,
                        "progress": progress_data.get("progress", 0),
                        "total": progress_data.get("total", 1),
                        "percentage": progress_data.get("percentage", 0),
                        "message": progress_data.get("message", ""),
                    }
                })
            except Exception as e:
                log.error(f"Failed to emit progress event: {e}")

    return on_progress


def format_mcp_tool_call_for_llm(
    tool_name: str,
    mcp_result: MCPToolResult
) -> str:
    """
    Format MCP tool result for LLM consumption

    This creates a clean text representation that:
    - Includes all text content
    - References media appropriately
    - Includes structured data when available
    - Respects annotation hints (audience, priority)
    """
    from .content_parser import MCPContentParser

    parts = []

    # Filter content based on audience annotation
    for block in mcp_result.content_blocks:
        audience = block.get_audience()

        # Skip blocks meant only for users
        if audience and "assistant" not in audience:
            continue

        if isinstance(block, TextContentBlock):
            parts.append(block.text)
        elif isinstance(block, ImageContentBlock):
            parts.append(f"[Image generated: {block.mime_type}]")
        elif isinstance(block, AudioContentBlock):
            parts.append(f"[Audio generated: {block.mime_type}]")
        elif isinstance(block, EmbeddedResourceBlock):
            if block.is_text_resource():
                parts.append(f"[Resource: {block.uri}]\n{block.text}")
            else:
                parts.append(f"[Resource: {block.uri}]")

    result_text = "\n".join(parts)

    # Add structured content if available
    if mcp_result.structured_content:
        structured_json = json.dumps(
            mcp_result.structured_content, indent=2, ensure_ascii=False
        )
        result_text += f"\n\n[Structured Output]\n{structured_json}"

    return result_text


# Example usage pattern for middleware.py:
"""
In middleware.py, around line 1285-1307, replace the MCP tool function creation:

# Original:
def make_tool_function(client, function_name):
    async def tool_function(**kwargs):
        return await client.call_tool(
            function_name,
            function_args=kwargs,
        )
    return tool_function

# Enhanced:
def make_tool_function(client, function_name):
    async def tool_function(**kwargs):
        # Import enhanced client
        from open_webui.utils.mcp.client_enhanced import EnhancedMCPClient
        from open_webui.utils.mcp.middleware_integration import (
            process_mcp_tool_result,
            create_mcp_progress_callback
        )

        # Create progress callback if event emitter available
        progress_callback = None
        if event_emitter:
            progress_callback = await create_mcp_progress_callback(
                event_emitter, function_name
            )

        # Call tool with enhanced client
        mcp_result = await client.call_tool(
            function_name,
            function_args=kwargs,
            progress_callback=progress_callback
        )

        # Process the result
        result_text, result_files, result_embeds = await process_mcp_tool_result(
            request,
            function_name,
            mcp_result,
            event_emitter,
            metadata,
            user
        )

        return {
            "text": result_text,
            "files": result_files,
            "embeds": result_embeds,
            "structured": mcp_result.structured_content,
            "mcp_result": mcp_result  # Keep full result for advanced processing
        }

    return tool_function
"""
