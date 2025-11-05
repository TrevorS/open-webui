"""
MCP Content Utilities - Working with native mcp.types

This module provides utility functions for working with MCP content types
using the native mcp.types classes directly, reducing boilerplate and ensuring
compatibility with the MCP specification.
"""

from typing import List, Optional, Dict, Any
import base64
import logging

# Use native MCP types
from mcp.types import (
    TextContent,
    ImageContent,
    AudioContent,
    EmbeddedResource,
    CallToolResult,
    Content,
)

log = logging.getLogger(__name__)


# ============================================================================
# Utility Functions for Content Blocks
# ============================================================================

def is_text_content(content: Content) -> bool:
    """Check if content is TextContent"""
    return isinstance(content, TextContent) or (
        isinstance(content, dict) and content.get("type") == "text"
    )


def is_image_content(content: Content) -> bool:
    """Check if content is ImageContent"""
    return isinstance(content, ImageContent) or (
        isinstance(content, dict) and content.get("type") == "image"
    )


def is_audio_content(content: Content) -> bool:
    """Check if content is AudioContent"""
    return isinstance(content, AudioContent) or (
        isinstance(content, dict) and content.get("type") == "audio"
    )


def is_resource_content(content: Content) -> bool:
    """Check if content is EmbeddedResource"""
    return isinstance(content, EmbeddedResource) or (
        isinstance(content, dict) and content.get("type") == "resource"
    )


def get_text_from_content(content: Content) -> str:
    """Extract text from a content block"""
    if isinstance(content, TextContent):
        return content.text
    elif isinstance(content, dict) and content.get("type") == "text":
        return content.get("text", "")
    return ""


def decode_image_data(content: ImageContent) -> bytes:
    """Decode base64 image data from ImageContent"""
    try:
        if isinstance(content, ImageContent):
            return base64.b64decode(content.data)
        elif isinstance(content, dict):
            return base64.b64decode(content.get("data", ""))
    except Exception as e:
        log.error(f"Failed to decode image data: {e}")
        return b""


def decode_audio_data(content: AudioContent) -> bytes:
    """Decode base64 audio data from AudioContent"""
    try:
        if isinstance(content, AudioContent):
            return base64.b64decode(content.data)
        elif isinstance(content, dict):
            return base64.b64decode(content.get("data", ""))
    except Exception as e:
        log.error(f"Failed to decode audio data: {e}")
        return b""


def get_file_extension_from_mime(mime_type: str) -> str:
    """Get file extension from MIME type"""
    mime_map = {
        # Images
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/gif": "gif",
        "image/webp": "webp",
        "image/svg+xml": "svg",
        # Audio
        "audio/wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/ogg": "ogg",
        "audio/webm": "webm",
        "audio/flac": "flac",
    }
    return mime_map.get(mime_type, mime_type.split("/")[-1] if "/" in mime_type else "bin")


def get_audience_from_annotations(content: Content) -> Optional[List[str]]:
    """Get audience annotation from content"""
    if isinstance(content, (TextContent, ImageContent, AudioContent, EmbeddedResource)):
        if content.annotations:
            return content.annotations.get("audience")
    elif isinstance(content, dict):
        annotations = content.get("annotations", {})
        if annotations:
            return annotations.get("audience")
    return None


def should_show_to_user(content: Content) -> bool:
    """Check if content should be shown to user based on audience annotation"""
    audience = get_audience_from_annotations(content)
    if audience is None:
        return True  # No annotation means show to everyone
    return "user" in audience


def should_show_to_assistant(content: Content) -> bool:
    """Check if content should be shown to assistant/LLM based on audience annotation"""
    audience = get_audience_from_annotations(content)
    if audience is None:
        return True  # No annotation means show to everyone
    return "assistant" in audience


# ============================================================================
# CallToolResult Processing
# ============================================================================

class MCPToolResult:
    """
    Wrapper around CallToolResult with utility methods

    This provides a convenient interface for working with CallToolResult
    while using the native MCP types underneath.
    """

    def __init__(self, result: CallToolResult):
        self.result = result

    @property
    def content(self) -> List[Content]:
        """Get content blocks"""
        return self.result.content

    @property
    def structured_content(self) -> Optional[Dict[str, Any]]:
        """Get structured content"""
        return self.result.structuredContent

    @property
    def is_error(self) -> bool:
        """Check if result is an error"""
        return self.result.isError

    def get_text_content(self) -> str:
        """Get all text content concatenated"""
        texts = []
        for content in self.content:
            if is_text_content(content):
                texts.append(get_text_from_content(content))
            elif is_resource_content(content) and isinstance(content, EmbeddedResource):
                # Check if it's a text resource
                resource = content.resource
                if hasattr(resource, 'text'):
                    texts.append(resource.text)
        return "\n".join(texts)

    def get_image_blocks(self) -> List[ImageContent]:
        """Get all image content blocks"""
        return [c for c in self.content if is_image_content(c)]

    def get_audio_blocks(self) -> List[AudioContent]:
        """Get all audio content blocks"""
        return [c for c in self.content if is_audio_content(c)]

    def get_resource_blocks(self) -> List[EmbeddedResource]:
        """Get all embedded resource blocks"""
        return [c for c in self.content if is_resource_content(c)]

    def has_media(self) -> bool:
        """Check if result contains any media (images/audio)"""
        return bool(self.get_image_blocks() or self.get_audio_blocks())

    def format_for_llm(self, include_structured: bool = True) -> str:
        """
        Format the result for LLM consumption

        This creates a clean text representation that:
        - Includes all text content meant for assistant
        - References media appropriately
        - Includes structured data if requested
        """
        parts = []

        for content in self.content:
            # Skip content not meant for assistant
            if not should_show_to_assistant(content):
                continue

            if is_text_content(content):
                parts.append(get_text_from_content(content))
            elif is_image_content(content):
                mime = content.mimeType if isinstance(content, ImageContent) else content.get("mimeType", "image")
                parts.append(f"[Image: {mime}]")
            elif is_audio_content(content):
                mime = content.mimeType if isinstance(content, AudioContent) else content.get("mimeType", "audio")
                parts.append(f"[Audio: {mime}]")
            elif is_resource_content(content):
                if isinstance(content, EmbeddedResource):
                    resource = content.resource
                    if hasattr(resource, 'uri'):
                        if hasattr(resource, 'text'):
                            parts.append(f"[Resource: {resource.uri}]\n{resource.text}")
                        else:
                            parts.append(f"[Resource: {resource.uri}]")

        result_text = "\n".join(parts)

        # Add structured content if available and requested
        if include_structured and self.structured_content:
            import json
            structured_json = json.dumps(
                self.structured_content, indent=2, ensure_ascii=False
            )
            result_text += f"\n\n[Structured Data]\n{structured_json}"

        return result_text

    def format_for_user(self) -> str:
        """
        Format the result for user display

        This includes only content meant for users.
        """
        parts = []

        for content in self.content:
            # Only include content meant for user
            if not should_show_to_user(content):
                continue

            if is_text_content(content):
                parts.append(get_text_from_content(content))
            elif is_image_content(content):
                parts.append("[Image]")
            elif is_audio_content(content):
                parts.append("[Audio]")

        return "\n".join(parts)


# ============================================================================
# Progress Tracking
# ============================================================================

class ProgressTracker:
    """
    Tracks progress for MCP tool execution
    """

    def __init__(self, token: str):
        self.token = token
        self.progress = 0.0
        self.total = 1.0
        self.message = ""
        self.updates: List[Dict[str, Any]] = []

    def update(self, progress: float, total: Optional[float] = None, message: str = ""):
        """Update progress"""
        self.progress = progress
        if total is not None:
            self.total = total
        self.message = message

        update = {
            "progress": progress,
            "total": self.total,
            "percentage": (progress / self.total * 100) if self.total > 0 else 0,
            "message": message
        }
        self.updates.append(update)
        return update

    def get_percentage(self) -> float:
        """Get current percentage"""
        if self.total > 0:
            return (self.progress / self.total) * 100
        return 0.0

    def is_complete(self) -> bool:
        """Check if progress is complete"""
        return self.progress >= self.total


# ============================================================================
# Utility: Create CallToolResult (for testing)
# ============================================================================

def create_text_result(text: str, is_error: bool = False) -> CallToolResult:
    """Helper to create a simple text CallToolResult"""
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        isError=is_error
    )


def create_image_result(
    image_data: str,
    mime_type: str = "image/png",
    description: Optional[str] = None
) -> CallToolResult:
    """Helper to create a CallToolResult with an image"""
    content = []
    if description:
        content.append(TextContent(type="text", text=description))
    content.append(ImageContent(type="image", data=image_data, mimeType=mime_type))
    return CallToolResult(content=content, isError=False)
