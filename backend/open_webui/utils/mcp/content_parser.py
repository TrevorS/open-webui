"""
MCP Content Parser - Handles all MCP content types with full fidelity

This module provides comprehensive parsing and processing of MCP CallToolResult
content, including:
- Text, Image, Audio content types
- Embedded resources
- Structured content with schema validation
- Progress reporting
- Annotations and metadata
"""

from typing import Any, Dict, List, Optional, Tuple
import base64
import logging

log = logging.getLogger(__name__)


class MCPContentBlock:
    """Base class for MCP content blocks"""

    def __init__(self, block_type: str, data: Dict[str, Any]):
        self.type = block_type
        self.annotations = data.get("annotations")
        self.meta = data.get("_meta")

    def has_annotation(self, key: str) -> bool:
        """Check if annotation exists"""
        return self.annotations and key in self.annotations

    def get_priority(self) -> Optional[float]:
        """Get priority annotation (0-1)"""
        if self.annotations and "priority" in self.annotations:
            return self.annotations["priority"]
        return None

    def get_audience(self) -> Optional[List[str]]:
        """Get intended audience (e.g., ['user'], ['assistant'])"""
        if self.annotations and "audience" in self.annotations:
            return self.annotations["audience"]
        return None


class TextContentBlock(MCPContentBlock):
    """Text content from MCP"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__("text", data)
        self.text = data.get("text", "")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "text",
            "text": self.text,
            "annotations": self.annotations,
            "meta": self.meta
        }

    def __str__(self) -> str:
        return self.text


class ImageContentBlock(MCPContentBlock):
    """Image content from MCP"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__("image", data)
        self.data = data.get("data", "")  # base64 encoded
        self.mime_type = data.get("mimeType", "image/png")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "image",
            "data": self.data,
            "mime_type": self.mime_type,
            "annotations": self.annotations,
            "meta": self.meta
        }

    def decode_data(self) -> bytes:
        """Decode base64 image data"""
        try:
            return base64.b64decode(self.data)
        except Exception as e:
            log.error(f"Failed to decode image data: {e}")
            return b""

    def get_file_extension(self) -> str:
        """Get file extension from mime type"""
        mime_map = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/jpg": "jpg",
            "image/gif": "gif",
            "image/webp": "webp",
            "image/svg+xml": "svg"
        }
        return mime_map.get(self.mime_type, "png")


class AudioContentBlock(MCPContentBlock):
    """Audio content from MCP"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__("audio", data)
        self.data = data.get("data", "")  # base64 encoded
        self.mime_type = data.get("mimeType", "audio/wav")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "audio",
            "data": self.data,
            "mime_type": self.mime_type,
            "annotations": self.annotations,
            "meta": self.meta
        }

    def decode_data(self) -> bytes:
        """Decode base64 audio data"""
        try:
            return base64.b64decode(self.data)
        except Exception as e:
            log.error(f"Failed to decode audio data: {e}")
            return b""

    def get_file_extension(self) -> str:
        """Get file extension from mime type"""
        mime_map = {
            "audio/wav": "wav",
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/ogg": "ogg",
            "audio/webm": "webm",
            "audio/flac": "flac"
        }
        return mime_map.get(self.mime_type, "wav")


class EmbeddedResourceBlock(MCPContentBlock):
    """Embedded resource from MCP"""

    def __init__(self, data: Dict[str, Any]):
        super().__init__("resource", data)
        self.resource = data.get("resource", {})

        # Parse resource content
        self.resource_type = self.resource.get("type")  # "text" or "blob"
        if self.resource_type == "text":
            self.uri = self.resource.get("uri", "")
            self.text = self.resource.get("text", "")
            self.mime_type = self.resource.get("mimeType")
        elif self.resource_type == "blob":
            self.uri = self.resource.get("uri", "")
            self.data = self.resource.get("blob", "")  # base64
            self.mime_type = self.resource.get("mimeType", "application/octet-stream")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "resource",
            "resource": self.resource,
            "annotations": self.annotations,
            "meta": self.meta
        }

    def is_text_resource(self) -> bool:
        return self.resource_type == "text"

    def is_blob_resource(self) -> bool:
        return self.resource_type == "blob"


class MCPToolResult:
    """
    Parsed MCP tool result with full content type support
    """

    def __init__(
        self,
        content_blocks: List[MCPContentBlock],
        structured_content: Optional[Dict[str, Any]] = None,
        is_error: bool = False,
        meta: Optional[Dict[str, Any]] = None
    ):
        self.content_blocks = content_blocks
        self.structured_content = structured_content
        self.is_error = is_error
        self.meta = meta

    def get_text_content(self) -> str:
        """Get all text content concatenated"""
        texts = []
        for block in self.content_blocks:
            if isinstance(block, TextContentBlock):
                texts.append(block.text)
            elif isinstance(block, EmbeddedResourceBlock) and block.is_text_resource():
                texts.append(block.text)
        return "\n".join(texts)

    def get_image_blocks(self) -> List[ImageContentBlock]:
        """Get all image content blocks"""
        return [b for b in self.content_blocks if isinstance(b, ImageContentBlock)]

    def get_audio_blocks(self) -> List[AudioContentBlock]:
        """Get all audio content blocks"""
        return [b for b in self.content_blocks if isinstance(b, AudioContentBlock)]

    def get_resource_blocks(self) -> List[EmbeddedResourceBlock]:
        """Get all embedded resource blocks"""
        return [b for b in self.content_blocks if isinstance(b, EmbeddedResourceBlock)]

    def has_media(self) -> bool:
        """Check if result contains any media (images/audio)"""
        return bool(self.get_image_blocks() or self.get_audio_blocks())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "content_blocks": [b.to_dict() for b in self.content_blocks],
            "structured_content": self.structured_content,
            "is_error": self.is_error,
            "meta": self.meta,
            "text": self.get_text_content(),
            "has_media": self.has_media()
        }


class MCPContentParser:
    """
    Parser for MCP CallToolResult content
    """

    @staticmethod
    def parse_content_block(block_data: Dict[str, Any]) -> MCPContentBlock:
        """Parse a single content block based on its type"""
        block_type = block_data.get("type")

        if block_type == "text":
            return TextContentBlock(block_data)
        elif block_type == "image":
            return ImageContentBlock(block_data)
        elif block_type == "audio":
            return AudioContentBlock(block_data)
        elif block_type == "resource":
            return EmbeddedResourceBlock(block_data)
        else:
            log.warning(f"Unknown content block type: {block_type}")
            # Return as text with the raw data
            return TextContentBlock({"text": str(block_data)})

    @staticmethod
    def parse_tool_result(result_data: Dict[str, Any]) -> MCPToolResult:
        """
        Parse a complete CallToolResult

        Args:
            result_data: Dictionary from result.model_dump(mode="json")

        Returns:
            MCPToolResult with parsed content blocks
        """
        content_list = result_data.get("content", [])
        structured = result_data.get("structuredContent")
        is_error = result_data.get("isError", False)
        meta = result_data.get("_meta")

        # Parse all content blocks
        content_blocks = []
        for block_data in content_list:
            try:
                block = MCPContentParser.parse_content_block(block_data)
                content_blocks.append(block)
            except Exception as e:
                log.error(f"Failed to parse content block: {e}")
                # Add as text to not lose information
                content_blocks.append(
                    TextContentBlock({"text": f"[Parse Error: {str(block_data)}]"})
                )

        return MCPToolResult(
            content_blocks=content_blocks,
            structured_content=structured,
            is_error=is_error,
            meta=meta
        )

    @staticmethod
    def format_for_llm(result: MCPToolResult) -> str:
        """
        Format the result as a string for the LLM

        This creates a text representation that:
        - Includes all text content
        - References media with [Image] / [Audio] placeholders
        - Includes structured content if available
        """
        parts = []

        # Add text content
        for block in result.content_blocks:
            if isinstance(block, TextContentBlock):
                parts.append(block.text)
            elif isinstance(block, ImageContentBlock):
                parts.append(f"[Image: {block.mime_type}]")
            elif isinstance(block, AudioContentBlock):
                parts.append(f"[Audio: {block.mime_type}]")
            elif isinstance(block, EmbeddedResourceBlock):
                if block.is_text_resource():
                    parts.append(f"[Resource: {block.uri}]\n{block.text}")
                else:
                    parts.append(f"[Resource: {block.uri} ({block.mime_type})]")

        text = "\n".join(parts)

        # Add structured content if available
        if result.structured_content:
            import json
            text += f"\n\n[Structured Data]\n{json.dumps(result.structured_content, indent=2)}"

        return text


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
