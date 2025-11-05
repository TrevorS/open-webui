"""
MCP Integration for Open WebUI Middleware

This module provides integration functions for processing MCP tool results
using native mcp.types and existing Open WebUI utilities.
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Tuple
from uuid import uuid4
import json

# Use native MCP types
from mcp.types import ImageContent, AudioContent, TextContent

# Use Open WebUI's existing file handling utilities
from open_webui.utils.files import (
    get_image_url_from_base64,
    get_file_url_from_base64,
)

# Our utilities
from .content_utils import (
    MCPToolResult,
    is_text_content,
    is_image_content,
    is_audio_content,
    is_resource_content,
    decode_image_data,
    decode_audio_data,
    get_text_from_content,
    get_file_extension_from_mime,
    should_show_to_assistant,
)

log = logging.getLogger(__name__)


async def process_mcp_result(
    request,
    tool_name: str,
    mcp_result: MCPToolResult,
    event_emitter: Optional[Callable] = None,
    metadata: Optional[Dict[str, Any]] = None,
    user=None,
) -> Tuple[str, List[Dict], List[str]]:
    """
    Process an MCP tool result using native types

    Args:
        request: FastAPI request object
        tool_name: Name of the tool that was called
        mcp_result: MCPToolResult wrapping native CallToolResult
        event_emitter: Event emitter for sending events to frontend
        metadata: Request metadata
        user: User object

    Returns:
        Tuple of (tool_result_text, tool_result_files, tool_result_embeds)
    """
    tool_result_files = []
    tool_result_embeds = []
    tool_result_text_parts = []

    # Process each content block using native types
    for content in mcp_result.content:
        try:
            if is_text_content(content):
                # Text content - just add to result
                text = get_text_from_content(content)
                tool_result_text_parts.append(text)

            elif is_image_content(content):
                # Image content - decode and upload using existing utilities
                image_file = await _process_image(
                    request, content, metadata, user, tool_name
                )
                if image_file:
                    tool_result_files.append(image_file)
                    tool_result_text_parts.append(
                        f"[Image: {image_file.get('name', 'image')}]"
                    )

            elif is_audio_content(content):
                # Audio content - decode and upload
                audio_file = await _process_audio(
                    request, content, metadata, user, tool_name
                )
                if audio_file:
                    tool_result_files.append(audio_file)
                    tool_result_text_parts.append(
                        f"[Audio: {audio_file.get('name', 'audio')}]"
                    )

            elif is_resource_content(content):
                # Embedded resource
                resource_text = _process_resource(content)
                if resource_text:
                    tool_result_text_parts.append(resource_text)

        except Exception as e:
            log.error(f"Error processing content block: {e}")
            tool_result_text_parts.append(f"[Error processing content: {str(e)}]")

    # Emit files event if we have files
    if tool_result_files and event_emitter:
        try:
            await event_emitter({
                "type": "files",
                "data": {
                    "files": tool_result_files,
                    "tool": tool_name
                },
            })
        except Exception as e:
            log.error(f"Failed to emit files event: {e}")

    # Combine text parts
    tool_result_text = "\n".join(tool_result_text_parts)

    # Add structured content if available
    if mcp_result.structured_content:
        try:
            structured_json = json.dumps(
                mcp_result.structured_content, indent=2, ensure_ascii=False
            )
            tool_result_text += f"\n\n[Structured Data]\n{structured_json}"
        except Exception as e:
            log.error(f"Failed to serialize structured content: {e}")

    return tool_result_text, tool_result_files, tool_result_embeds


async def _process_image(
    request,
    content: ImageContent,
    metadata: Optional[Dict],
    user,
    tool_name: str
) -> Optional[Dict[str, Any]]:
    """Process an image content block using existing Open WebUI utilities"""
    try:
        # Get mime type and decode data
        mime_type = content.mimeType if isinstance(content, ImageContent) else content.get("mimeType", "image/png")
        image_data = decode_image_data(content)

        if not image_data:
            return None

        # Convert to base64 data URL format that Open WebUI expects
        import base64
        b64_data = base64.b64encode(image_data).decode('ascii')
        data_url = f"data:{mime_type};base64,{b64_data}"

        # Use Open WebUI's existing image upload utility
        image_url = get_image_url_from_base64(
            request, data_url, metadata or {}, user
        )

        if not image_url:
            return None

        # Return file entry in Open WebUI format
        return {
            "type": "image",
            "name": f"mcp_{tool_name}_{uuid4().hex[:8]}.{get_file_extension_from_mime(mime_type)}",
            "url": image_url,
            "mime_type": mime_type,
        }

    except Exception as e:
        log.error(f"Failed to process image content: {e}")
        return None


async def _process_audio(
    request,
    content: AudioContent,
    metadata: Optional[Dict],
    user,
    tool_name: str
) -> Optional[Dict[str, Any]]:
    """Process an audio content block"""
    try:
        # Get mime type and decode data
        mime_type = content.mimeType if isinstance(content, AudioContent) else content.get("mimeType", "audio/wav")
        audio_data = decode_audio_data(content)

        if not audio_data:
            return None

        # Convert to base64 data URL format
        import base64
        b64_data = base64.b64encode(audio_data).decode('ascii')
        data_url = f"data:{mime_type};base64,{b64_data}"

        # Use Open WebUI's existing file upload utility
        # Note: audio might need special handling vs images
        file_url = get_file_url_from_base64(
            request, data_url, metadata or {}, user
        )

        if not file_url:
            return None

        return {
            "type": "audio",
            "name": f"mcp_{tool_name}_{uuid4().hex[:8]}.{get_file_extension_from_mime(mime_type)}",
            "url": file_url,
            "mime_type": mime_type,
        }

    except Exception as e:
        log.error(f"Failed to process audio content: {e}")
        return None


def _process_resource(content) -> Optional[str]:
    """Process an embedded resource"""
    try:
        # Access the resource
        if hasattr(content, 'resource'):
            resource = content.resource
            uri = getattr(resource, 'uri', 'unknown')

            # Check if it's a text resource
            if hasattr(resource, 'text'):
                return f"[Resource: {uri}]\n{resource.text}"
            else:
                # Binary resource
                mime_type = getattr(resource, 'mimeType', 'unknown')
                return f"[Resource: {uri} ({mime_type})]"

    except Exception as e:
        log.error(f"Failed to process resource: {e}")

    return None


def create_progress_callback(
    event_emitter: Optional[Callable],
    tool_name: str
) -> Optional[Callable]:
    """
    Create a progress callback that emits progress events

    Args:
        event_emitter: Event emitter function
        tool_name: Name of the tool for progress tracking

    Returns:
        Async callback function for progress updates or None
    """
    if not event_emitter:
        return None

    async def on_progress(progress_data: Dict[str, Any]):
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


def format_for_llm(mcp_result: MCPToolResult) -> str:
    """
    Format MCP tool result for LLM consumption

    Uses the MCPToolResult utility to create a clean text representation
    that respects audience annotations and includes structured data.
    """
    return mcp_result.format_for_llm(include_structured=True)
