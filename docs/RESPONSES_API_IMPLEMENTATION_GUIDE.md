# OpenAI Responses API - Open WebUI Implementation Guide

**Goal:** Add support for OpenAI's Responses API to Open WebUI while maintaining backward compatibility with Chat Completions API.

**Strategy:** Hybrid approach - support both APIs, make Responses API opt-in initially.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Phase 1: Core Backend](#phase-1-core-backend)
3. [Phase 2: Frontend Integration](#phase-2-frontend-integration)
4. [Phase 3: Tool Support](#phase-3-tool-support)
5. [Phase 4: Advanced Features](#phase-4-advanced-features)
6. [Testing Strategy](#testing-strategy)
7. [Migration Path](#migration-path)

---

## Architecture Overview

### Current Architecture

```
User → Frontend → Backend → OpenAI Chat Completions API
                     ↓
                 Database (stores full message history)
```

### New Architecture (Hybrid)

```
User → Frontend → Backend → [Router Decision] → OpenAI Chat Completions API (default)
                     ↓                        → OpenAI Responses API (opt-in)
                 Database (stores messages + response_ids)
```

### Key Design Decisions

1. **Backward Compatible** - Existing chats continue using Chat Completions
2. **Opt-in per Model** - Admin can enable Responses API for specific models
3. **Format Abstraction** - Frontend doesn't know which API is used
4. **Dual Storage** - Store both message history and response_ids for flexibility
5. **Gradual Tool Rollout** - Enable tools incrementally (MCP → Code → Search → etc.)

---

## Phase 1: Core Backend

**Timeline:** 2-3 weeks
**Effort:** 60-80 hours

### 1.1 Configuration Layer

**File:** `/backend/open_webui/config.py`

Add configuration variables around line 1062 (after OPENAI_API_CONFIGS):

```python
####################################
# RESPONSES API CONFIGURATION
####################################

ENABLE_RESPONSES_API = PersistentConfig(
    "ENABLE_RESPONSES_API",
    "openai.responses_api.enable",
    False,  # Default: disabled for backward compatibility
)

RESPONSES_API_MODELS = PersistentConfig(
    "RESPONSES_API_MODELS",
    "openai.responses_api.models",
    [],  # List of model IDs that should use Responses API
    # Example: ["gpt-4o", "gpt-4.1", "o3"]
)

RESPONSES_API_DEFAULT_STATEFUL = PersistentConfig(
    "RESPONSES_API_DEFAULT_STATEFUL",
    "openai.responses_api.default_stateful",
    True,  # Use stateful mode by default when Responses API enabled
)

RESPONSES_API_ENABLED_TOOLS = PersistentConfig(
    "RESPONSES_API_ENABLED_TOOLS",
    "openai.responses_api.enabled_tools",
    [],  # List of enabled tool types
    # Example: ["web_search_preview", "code_interpreter"]
)

RESPONSES_API_MCP_SERVERS = PersistentConfig(
    "RESPONSES_API_MCP_SERVERS",
    "openai.responses_api.mcp_servers",
    [],  # List of MCP server configurations
    # Example: [{"label": "stripe", "url": "https://mcp.stripe.com", ...}]
)
```

**Environment variables to support:**

```bash
# .env file additions
ENABLE_RESPONSES_API=false
RESPONSES_API_MODELS=gpt-4o,gpt-4.1,o3
RESPONSES_API_DEFAULT_STATEFUL=true
RESPONSES_API_ENABLED_TOOLS=web_search_preview,code_interpreter
```

### 1.2 Database Schema Updates

**File:** `/backend/open_webui/models/responses.py` (new file)

```python
from sqlalchemy import Column, String, Integer, Text, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
from open_webui.internal.db import Base

class Response(Base):
    """
    Store OpenAI Responses API response metadata for stateful conversations.

    This allows tracking response_ids and enabling stateful conversation
    continuation without sending full message history.
    """
    __tablename__ = "responses"

    # Primary response data
    id = Column(String, primary_key=True)  # OpenAI response_id (resp_xxx)
    chat_id = Column(String, ForeignKey("chat.id"), nullable=False)
    user_id = Column(String, ForeignKey("user.id"), nullable=False)
    message_id = Column(String, nullable=True)  # Related message in chat

    # Response metadata
    model = Column(String, nullable=False)
    created_at = Column(Integer, nullable=False)  # Unix timestamp
    status = Column(String, default="completed")  # queued, in_progress, completed, failed

    # Stateful conversation tracking
    previous_response_id = Column(String, nullable=True)
    is_stored_on_openai = Column(Boolean, default=False)  # store=true was used

    # Response content (cached)
    output_text = Column(Text, nullable=True)
    usage_prompt_tokens = Column(Integer, nullable=True)
    usage_completion_tokens = Column(Integer, nullable=True)
    usage_total_tokens = Column(Integer, nullable=True)

    # Tool usage tracking
    tools_used = Column(JSON, nullable=True)  # List of tools called
    tool_costs = Column(JSON, nullable=True)  # Cost breakdown by tool

    # Additional metadata
    metadata = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)

    # Relationships
    chat = relationship("Chat", back_populates="responses")
    user = relationship("User")

# Update Chat model to include responses relationship
# In /backend/open_webui/models/chats.py, add:
# responses = relationship("Response", back_populates="chat")
```

**Migration:**

```bash
# Create migration
cd backend
alembic revision -m "add_responses_api_support"

# Apply migration
alembic upgrade head
```

### 1.3 Response Converter Utility

**File:** `/backend/open_webui/utils/responses_api.py` (new file)

```python
"""
Utilities for OpenAI Responses API integration.

Handles format conversion between Chat Completions API and Responses API,
and provides helper functions for stateful conversation management.
"""

from typing import Dict, List, Optional, Any
import logging

log = logging.getLogger(__name__)


def openai_to_responses_format(
    messages: List[Dict],
    model: str,
    tools: Optional[List[Dict]] = None,
    previous_response_id: Optional[str] = None,
    stateful: bool = True,
    **kwargs
) -> Dict:
    """
    Convert Chat Completions format to Responses API format.

    Args:
        messages: Array of message objects (Chat Completions format)
        model: Model ID
        tools: Optional tool definitions
        previous_response_id: For continuing stateful conversations
        stateful: Whether to use stateful mode (input) or stateless (messages)
        **kwargs: Additional parameters (temperature, max_tokens, etc.)

    Returns:
        Request body for Responses API
    """
    # Extract system message if present
    system_message = None
    conversation_messages = []

    for msg in messages:
        if msg.get("role") == "system":
            system_message = msg.get("content")
        else:
            conversation_messages.append(msg)

    # Build base request
    request = {
        "model": model,
    }

    if stateful and previous_response_id:
        # Stateful mode - use input and previous_response_id
        # Only include the latest user message as input
        latest_message = conversation_messages[-1] if conversation_messages else {"content": ""}
        request["input"] = latest_message.get("content", "")
        request["previous_response_id"] = previous_response_id
        request["store"] = True
    elif stateful and len(conversation_messages) == 1:
        # First message in stateful conversation
        request["input"] = conversation_messages[0].get("content", "")
        request["store"] = True
    else:
        # Stateless mode - use messages array
        request["messages"] = conversation_messages

    # Add system instructions if present
    if system_message:
        request["instructions"] = system_message

    # Add tools if provided
    if tools:
        request["tools"] = tools

    # Add additional parameters
    if "temperature" in kwargs:
        request["temperature"] = kwargs["temperature"]
    if "max_tokens" in kwargs:
        request["max_output_tokens"] = kwargs["max_tokens"]
    if "stream" in kwargs:
        request["stream"] = kwargs["stream"]

    return request


def responses_to_openai_format(response: Dict) -> Dict:
    """
    Convert Responses API response to Chat Completions format.

    This ensures frontend compatibility - frontend expects Chat Completions format.

    Args:
        response: Response from Responses API

    Returns:
        Response in Chat Completions format
    """
    return {
        "id": response.get("id", ""),
        "object": "chat.completion",
        "created": response.get("created_at", 0),
        "model": response.get("model", ""),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.get("output_text", ""),
                },
                "finish_reason": "stop" if response.get("status") == "completed" else "length",
            }
        ],
        "usage": {
            "prompt_tokens": response.get("usage", {}).get("prompt_tokens", 0),
            "completion_tokens": response.get("usage", {}).get("completion_tokens", 0),
            "total_tokens": response.get("usage", {}).get("total_tokens", 0),
        },
        # Store response_id in metadata for tracking
        "metadata": {
            "response_id": response.get("id"),
            "previous_response_id": response.get("previous_response_id"),
        }
    }


def parse_responses_stream_event(event_line: str) -> Optional[Dict]:
    """
    Parse a single SSE event from Responses API stream.

    Responses API uses full SSE format:
        event: response.output_text.delta
        data: {"delta": {"text": "Hello"}}

    Args:
        event_line: Raw event line from stream

    Returns:
        Parsed event dict or None
    """
    if event_line.startswith("event: "):
        return {"type": "event", "event": event_line[7:].strip()}
    elif event_line.startswith("data: "):
        import json
        try:
            return {"type": "data", "data": json.loads(event_line[6:])}
        except json.JSONDecodeError:
            log.warning(f"Failed to parse SSE data: {event_line}")
            return None
    return None


async def convert_responses_stream_to_openai_stream(stream):
    """
    Convert Responses API streaming format to Chat Completions streaming format.

    Responses API streams:
        event: response.output_text.delta
        data: {"delta": {"text": "Hello"}}

    Chat Completions expects:
        data: {"choices": [{"delta": {"content": "Hello"}}]}

    Args:
        stream: AsyncIterator of Responses API events

    Yields:
        Lines in Chat Completions streaming format
    """
    current_event = None

    async for line in stream:
        line = line.decode('utf-8').strip() if isinstance(line, bytes) else line.strip()

        if not line:
            continue

        parsed = parse_responses_stream_event(line)
        if not parsed:
            continue

        if parsed["type"] == "event":
            current_event = parsed["event"]
        elif parsed["type"] == "data":
            data = parsed["data"]

            # Convert output_text deltas to Chat Completions format
            if current_event == "response.output_text.delta":
                text = data.get("delta", {}).get("text", "")
                if text:
                    yield f"data: {json.dumps({'choices': [{'delta': {'content': text}}]})}\n\n"

            # Handle completion event
            elif current_event == "response.completed":
                yield "data: [DONE]\n\n"


def get_enabled_tools(config) -> List[Dict]:
    """
    Build tools array based on configuration.

    Args:
        config: Application configuration object

    Returns:
        List of tool definitions for Responses API
    """
    tools = []
    enabled_tool_types = config.RESPONSES_API_ENABLED_TOOLS.value

    if "web_search_preview" in enabled_tool_types:
        tools.append({"type": "web_search_preview"})

    if "code_interpreter" in enabled_tool_types:
        tools.append({
            "type": "code_interpreter",
            "container": {"type": "auto"}
        })

    if "file_search" in enabled_tool_types:
        # File search requires file_ids - will be added per-request
        tools.append({"type": "file_search"})

    if "image_generation" in enabled_tool_types:
        tools.append({
            "type": "image_generation",
            "model": "gpt-image-1"
        })

    # Add MCP servers
    for mcp_config in config.RESPONSES_API_MCP_SERVERS.value:
        tools.append({
            "type": "mcp",
            "server_label": mcp_config.get("label"),
            "server_url": mcp_config.get("url"),
            "require_approval": mcp_config.get("require_approval", "never"),
            "headers": mcp_config.get("headers", {}),
        })

    return tools


def should_use_responses_api(model_id: str, config) -> bool:
    """
    Determine if a model should use Responses API.

    Args:
        model_id: The model identifier
        config: Application configuration

    Returns:
        True if Responses API should be used
    """
    if not config.ENABLE_RESPONSES_API.value:
        return False

    enabled_models = config.RESPONSES_API_MODELS.value

    # Empty list = all models
    if not enabled_models:
        return True

    # Check if model is in enabled list
    return model_id in enabled_models


import json
```

### 1.4 Responses Router

**File:** `/backend/open_webui/routers/responses.py` (new file)

```python
"""
OpenAI Responses API integration router.

Provides endpoints for:
- Creating responses (stateful and stateless)
- Retrieving responses (for background mode)
- Configuration management
- Tool management
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from openai import OpenAI, AsyncOpenAI

from open_webui.models.responses import Response
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.responses_api import (
    openai_to_responses_format,
    responses_to_openai_format,
    should_use_responses_api,
    get_enabled_tools,
)

log = logging.getLogger(__name__)
router = APIRouter()


####################################
# Configuration Endpoints
####################################

@router.get("/config")
async def get_responses_config(
    request: Request,
    user=Depends(get_admin_user)
):
    """Get Responses API configuration (admin only)."""
    return {
        "ENABLE_RESPONSES_API": request.app.state.config.ENABLE_RESPONSES_API.value,
        "RESPONSES_API_MODELS": request.app.state.config.RESPONSES_API_MODELS.value,
        "RESPONSES_API_DEFAULT_STATEFUL": request.app.state.config.RESPONSES_API_DEFAULT_STATEFUL.value,
        "RESPONSES_API_ENABLED_TOOLS": request.app.state.config.RESPONSES_API_ENABLED_TOOLS.value,
        "RESPONSES_API_MCP_SERVERS": request.app.state.config.RESPONSES_API_MCP_SERVERS.value,
    }


class ResponsesConfigForm(BaseModel):
    ENABLE_RESPONSES_API: Optional[bool] = None
    RESPONSES_API_MODELS: Optional[list[str]] = None
    RESPONSES_API_DEFAULT_STATEFUL: Optional[bool] = None
    RESPONSES_API_ENABLED_TOOLS: Optional[list[str]] = None
    RESPONSES_API_MCP_SERVERS: Optional[list[dict]] = None


@router.post("/config/update")
async def update_responses_config(
    request: Request,
    form_data: ResponsesConfigForm,
    user=Depends(get_admin_user)
):
    """Update Responses API configuration (admin only)."""
    if form_data.ENABLE_RESPONSES_API is not None:
        request.app.state.config.ENABLE_RESPONSES_API.value = form_data.ENABLE_RESPONSES_API

    if form_data.RESPONSES_API_MODELS is not None:
        request.app.state.config.RESPONSES_API_MODELS.value = form_data.RESPONSES_API_MODELS

    if form_data.RESPONSES_API_DEFAULT_STATEFUL is not None:
        request.app.state.config.RESPONSES_API_DEFAULT_STATEFUL.value = form_data.RESPONSES_API_DEFAULT_STATEFUL

    if form_data.RESPONSES_API_ENABLED_TOOLS is not None:
        request.app.state.config.RESPONSES_API_ENABLED_TOOLS.value = form_data.RESPONSES_API_ENABLED_TOOLS

    if form_data.RESPONSES_API_MCP_SERVERS is not None:
        request.app.state.config.RESPONSES_API_MCP_SERVERS.value = form_data.RESPONSES_API_MCP_SERVERS

    return await get_responses_config(request, user)


####################################
# Response Creation
####################################

@router.post("/create")
async def create_response(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user)
):
    """
    Create a response using Responses API.

    This is typically called internally by the chat router when
    Responses API is enabled for a model.
    """
    model_id = form_data.get("model")

    if not should_use_responses_api(model_id, request.app.state.config):
        raise HTTPException(
            status_code=400,
            detail="Responses API not enabled for this model"
        )

    # Get OpenAI API key
    # Reuse existing OpenAI configuration
    try:
        idx = 0
        url = request.app.state.config.OPENAI_API_BASE_URLS.value[idx]
        key = request.app.state.config.OPENAI_API_KEYS.value[idx]
    except (IndexError, AttributeError):
        raise HTTPException(
            status_code=500,
            detail="OpenAI API not configured"
        )

    # Get previous response_id if this is continuing a conversation
    chat_id = form_data.get("chat_id")
    previous_response_id = None

    if chat_id:
        # Look up the last response for this chat
        from open_webui.models.responses import Response as ResponseModel
        last_response = (
            ResponseModel.query
            .filter_by(chat_id=chat_id)
            .order_by(ResponseModel.created_at.desc())
            .first()
        )
        if last_response and last_response.is_stored_on_openai:
            previous_response_id = last_response.id

    # Build tools array
    tools = get_enabled_tools(request.app.state.config)

    # Convert format
    stateful = request.app.state.config.RESPONSES_API_DEFAULT_STATEFUL.value
    responses_request = openai_to_responses_format(
        messages=form_data.get("messages", []),
        model=model_id,
        tools=tools if tools else None,
        previous_response_id=previous_response_id,
        stateful=stateful,
        temperature=form_data.get("temperature"),
        max_tokens=form_data.get("max_tokens"),
        stream=form_data.get("stream", False),
    )

    # Make request to OpenAI Responses API
    client = AsyncOpenAI(api_key=key, base_url=url)

    try:
        response = await client.responses.create(**responses_request)

        # Store response metadata in database
        if not form_data.get("stream"):
            # For non-streaming, we have the full response
            response_record = ResponseModel(
                id=response.id,
                chat_id=chat_id,
                user_id=user.id,
                model=response.model,
                created_at=response.created_at,
                status=response.status,
                previous_response_id=previous_response_id,
                is_stored_on_openai=stateful,
                output_text=response.output_text,
                usage_prompt_tokens=response.usage.prompt_tokens if response.usage else None,
                usage_completion_tokens=response.usage.completion_tokens if response.usage else None,
                usage_total_tokens=response.usage.total_tokens if response.usage else None,
            )
            # Save to database
            # response_record.save()  # Implement based on your ORM

        # Convert to Chat Completions format for frontend compatibility
        return responses_to_openai_format(response.model_dump())

    except Exception as e:
        log.exception(f"Responses API error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Responses API error: {str(e)}"
        )


####################################
# Background Mode Support
####################################

@router.get("/retrieve/{response_id}")
async def retrieve_response(
    request: Request,
    response_id: str,
    user=Depends(get_verified_user)
):
    """
    Retrieve a response by ID (for background mode polling).
    """
    # Get OpenAI client
    try:
        idx = 0
        key = request.app.state.config.OPENAI_API_KEYS.value[idx]
        url = request.app.state.config.OPENAI_API_BASE_URLS.value[idx]
    except (IndexError, AttributeError):
        raise HTTPException(
            status_code=500,
            detail="OpenAI API not configured"
        )

    client = AsyncOpenAI(api_key=key, base_url=url)

    try:
        response = await client.responses.retrieve(response_id)
        return responses_to_openai_format(response.model_dump())
    except Exception as e:
        log.exception(f"Failed to retrieve response: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Response not found: {str(e)}"
        )
```

### 1.5 Update OpenAI Router

**File:** `/backend/open_webui/routers/openai.py`

Modify the `generate_chat_completion` function (around line 804):

```python
@router.post("/chat/completions")
async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
    bypass_filter: Optional[bool] = False,
):
    # ... existing code ...

    model_id = form_data.get("model")

    # NEW: Check if we should use Responses API
    from open_webui.utils.responses_api import should_use_responses_api
    if should_use_responses_api(model_id, request.app.state.config):
        # Delegate to Responses API
        from open_webui.routers.responses import create_response
        return await create_response(request, form_data, user)

    # ... existing Chat Completions code continues ...
```

### 1.6 Register Router

**File:** `/backend/open_webui/main.py`

Add router registration around line 1284:

```python
from open_webui.routers import openai, ollama, responses

app.include_router(ollama.router, prefix="/ollama", tags=["ollama"])
app.include_router(openai.router, prefix="/openai", tags=["openai"])
app.include_router(responses.router, prefix="/responses", tags=["responses"])  # NEW
```

---

## Phase 2: Frontend Integration

**Timeline:** 1-2 weeks
**Effort:** 40-50 hours

### 2.1 API Client

**File:** `/src/lib/apis/responses/index.ts` (new file)

```typescript
import { WEBUI_BASE_URL } from '$lib/constants';

export interface ResponsesConfig {
    ENABLE_RESPONSES_API: boolean;
    RESPONSES_API_MODELS: string[];
    RESPONSES_API_DEFAULT_STATEFUL: boolean;
    RESPONSES_API_ENABLED_TOOLS: string[];
    RESPONSES_API_MCP_SERVERS: Array<{
        label: string;
        url: string;
        require_approval?: string;
        headers?: Record<string, string>;
    }>;
}

export const getResponsesConfig = async (token: string): Promise<ResponsesConfig> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/responses/config`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    });

    if (!res.ok) throw await res.json();
    return res.json();
};

export const updateResponsesConfig = async (
    token: string,
    config: Partial<ResponsesConfig>
): Promise<ResponsesConfig> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/responses/config/update`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(config)
    });

    if (!res.ok) throw await res.json();
    return res.json();
};

export const createResponse = async (
    token: string,
    body: {
        model: string;
        messages: Array<{ role: string; content: string }>;
        chat_id?: string;
        stream?: boolean;
        temperature?: number;
        max_tokens?: number;
    }
): Promise<any> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/responses/create`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(body)
    });

    if (!res.ok) throw await res.json();
    return res.json();
};

export const retrieveResponse = async (
    token: string,
    responseId: string
): Promise<any> => {
    const res = await fetch(`${WEBUI_BASE_URL}/api/responses/retrieve/${responseId}`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        }
    });

    if (!res.ok) throw await res.json();
    return res.json();
};
```

### 2.2 Admin Settings Component

**File:** `/src/lib/components/admin/Settings/ResponsesApi.svelte` (new file)

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import { getResponsesConfig, updateResponsesConfig } from '$lib/apis/responses';
    import type { ResponsesConfig } from '$lib/apis/responses';
    import { toast } from 'svelte-sonner';

    export let saveHandler: () => void;

    let loading = false;
    let config: ResponsesConfig = {
        ENABLE_RESPONSES_API: false,
        RESPONSES_API_MODELS: [],
        RESPONSES_API_DEFAULT_STATEFUL: true,
        RESPONSES_API_ENABLED_TOOLS: [],
        RESPONSES_API_MCP_SERVERS: []
    };

    let newModelId = '';
    let availableTools = [
        { id: 'web_search_preview', name: 'Web Search', description: 'Built-in web search' },
        { id: 'code_interpreter', name: 'Code Interpreter', description: 'Execute Python code ($0.03/container)' },
        { id: 'file_search', name: 'File Search', description: 'Vector-based document search ($0.10/GB/day)' },
        { id: 'image_generation', name: 'Image Generation', description: 'Generate images with gpt-image-1' }
    ];

    onMount(async () => {
        await loadConfig();
    });

    const loadConfig = async () => {
        loading = true;
        try {
            const token = localStorage.getItem('token');
            config = await getResponsesConfig(token);
        } catch (error) {
            console.error('Failed to load config:', error);
            toast.error('Failed to load Responses API configuration');
        } finally {
            loading = false;
        }
    };

    const save = async () => {
        loading = true;
        try {
            const token = localStorage.getItem('token');
            await updateResponsesConfig(token, config);
            toast.success('Responses API configuration saved');
            if (saveHandler) saveHandler();
        } catch (error) {
            console.error('Failed to save config:', error);
            toast.error('Failed to save configuration');
        } finally {
            loading = false;
        }
    };

    const addModel = () => {
        if (newModelId && !config.RESPONSES_API_MODELS.includes(newModelId)) {
            config.RESPONSES_API_MODELS = [...config.RESPONSES_API_MODELS, newModelId];
            newModelId = '';
        }
    };

    const removeModel = (modelId: string) => {
        config.RESPONSES_API_MODELS = config.RESPONSES_API_MODELS.filter(m => m !== modelId);
    };

    const toggleTool = (toolId: string) => {
        if (config.RESPONSES_API_ENABLED_TOOLS.includes(toolId)) {
            config.RESPONSES_API_ENABLED_TOOLS = config.RESPONSES_API_ENABLED_TOOLS.filter(t => t !== toolId);
        } else {
            config.RESPONSES_API_ENABLED_TOOLS = [...config.RESPONSES_API_ENABLED_TOOLS, toolId];
        }
    };
</script>

<div class="flex flex-col gap-4">
    <div class="space-y-2">
        <div class="flex items-center gap-2">
            <input
                type="checkbox"
                bind:checked={config.ENABLE_RESPONSES_API}
                id="enable-responses-api"
                class="checkbox"
            />
            <label for="enable-responses-api" class="font-medium">
                Enable OpenAI Responses API
            </label>
        </div>
        <p class="text-sm text-gray-500">
            Use OpenAI's new Responses API with stateful conversations and built-in tools.
            This is optional and backward compatible with existing chats.
        </p>
    </div>

    {#if config.ENABLE_RESPONSES_API}
        <!-- Stateful Mode -->
        <div class="space-y-2">
            <div class="flex items-center gap-2">
                <input
                    type="checkbox"
                    bind:checked={config.RESPONSES_API_DEFAULT_STATEFUL}
                    id="default-stateful"
                    class="checkbox"
                />
                <label for="default-stateful" class="font-medium">
                    Use stateful conversations by default
                </label>
            </div>
            <p class="text-sm text-gray-500">
                Store conversation history on OpenAI servers. Reduces token usage by 40-80%.
            </p>
        </div>

        <!-- Model Selection -->
        <div class="space-y-2">
            <label class="font-medium">Enabled Models</label>
            <p class="text-sm text-gray-500">
                Select which models should use Responses API. Leave empty to enable for all models.
            </p>

            <div class="flex gap-2">
                <input
                    type="text"
                    bind:value={newModelId}
                    placeholder="gpt-4o, gpt-4.1, o3..."
                    class="input flex-1"
                    on:keypress={(e) => e.key === 'Enter' && addModel()}
                />
                <button on:click={addModel} class="btn btn-primary">Add</button>
            </div>

            <div class="flex flex-wrap gap-2">
                {#each config.RESPONSES_API_MODELS as modelId}
                    <div class="badge badge-lg gap-2">
                        {modelId}
                        <button on:click={() => removeModel(modelId)} class="btn btn-ghost btn-xs">
                            ×
                        </button>
                    </div>
                {/each}
            </div>
        </div>

        <!-- Tools -->
        <div class="space-y-2">
            <label class="font-medium">Available Tools</label>
            <p class="text-sm text-gray-500">
                Enable built-in tools for AI to use during conversations.
            </p>

            {#each availableTools as tool}
                <div class="flex items-start gap-2 p-2 border rounded">
                    <input
                        type="checkbox"
                        checked={config.RESPONSES_API_ENABLED_TOOLS.includes(tool.id)}
                        on:change={() => toggleTool(tool.id)}
                        id={`tool-${tool.id}`}
                        class="checkbox mt-1"
                    />
                    <label for={`tool-${tool.id}`} class="flex-1">
                        <div class="font-medium">{tool.name}</div>
                        <div class="text-sm text-gray-500">{tool.description}</div>
                    </label>
                </div>
            {/each}
        </div>
    {/if}

    <div class="flex justify-end gap-2">
        <button on:click={loadConfig} class="btn btn-secondary" disabled={loading}>
            Reset
        </button>
        <button on:click={save} class="btn btn-primary" disabled={loading}>
            {loading ? 'Saving...' : 'Save Configuration'}
        </button>
    </div>
</div>
```

### 2.3 Integrate into Admin Settings

**File:** `/src/lib/components/admin/Settings.svelte` (or wherever admin settings are)

Add a new tab/section for Responses API:

```svelte
<!-- Add to settings navigation -->
<button on:click={() => selectedTab = 'responses'}>
    Responses API
</button>

<!-- Add to settings content -->
{#if selectedTab === 'responses'}
    <ResponsesApi saveHandler={() => loadSettings()} />
{/if}
```

---

## Phase 3: Tool Support

**Timeline:** 3-4 weeks
**Effort:** 80-100 hours

### Implementation order:
1. Web Search (simplest)
2. Code Interpreter
3. File Search
4. Image Generation
5. MCP Servers (most complex)

*(Detailed implementation for each tool to be added)*

---

## Phase 4: Advanced Features

**Timeline:** 2-3 weeks
**Effort:** 60-80 hours

### Features:
1. Streaming improvements
2. Background mode with polling
3. Cost tracking dashboard
4. Tool result visualization
5. MCP server marketplace

---

## Testing Strategy

### Unit Tests

```python
# tests/test_responses_api.py

def test_openai_to_responses_format_stateful():
    messages = [
        {"role": "user", "content": "Hello"}
    ]
    result = openai_to_responses_format(
        messages=messages,
        model="gpt-4o",
        stateful=True
    )
    assert result["input"] == "Hello"
    assert result["store"] == True
    assert "messages" not in result

def test_responses_to_openai_format():
    response = {
        "id": "resp_123",
        "created_at": 1234567890,
        "model": "gpt-4o",
        "output_text": "Hello!",
        "status": "completed",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }
    result = responses_to_openai_format(response)
    assert result["choices"][0]["message"]["content"] == "Hello!"
    assert result["usage"]["total_tokens"] == 15
```

### Integration Tests

```python
# tests/integration/test_responses_endpoint.py

async def test_create_response_stateful(client, admin_user):
    # Enable Responses API
    await client.post(
        "/api/responses/config/update",
        json={"ENABLE_RESPONSES_API": True},
        headers={"Authorization": f"Bearer {admin_user.token}"}
    )

    # Create first response
    response = await client.post(
        "/api/responses/create",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
            "chat_id": "test-chat-1"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "metadata" in data
    assert "response_id" in data["metadata"]
```

---

## Migration Path

### For Existing Users

1. **No Breaking Changes** - Existing chats continue using Chat Completions
2. **Opt-in** - Admin must explicitly enable Responses API
3. **Per-model** - Can enable for specific models only
4. **Gradual rollout** - Tools can be enabled incrementally

### For New Deployments

1. Default: Responses API disabled (same as current behavior)
2. Documentation on how to enable
3. Recommended models for Responses API (GPT-4o, GPT-4.1, o-series)

---

## Timeline Summary

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1: Core Backend | 2-3 weeks | Router, config, database, format conversion |
| Phase 2: Frontend | 1-2 weeks | Admin UI, API client |
| Phase 3: Tools | 3-4 weeks | Web search, code interpreter, file search, image gen, MCP |
| Phase 4: Advanced | 2-3 weeks | Streaming, background mode, cost tracking, visualizations |
| **Total** | **8-12 weeks** | **Full feature parity** |

---

## Success Metrics

- [ ] Responses API can be enabled/disabled without affecting existing functionality
- [ ] Stateful conversations reduce token usage by 40-80%
- [ ] All built-in tools functional (MCP, code, search, image, web)
- [ ] Streaming works correctly with new event format
- [ ] Background mode polling works for long-running tasks
- [ ] Cost tracking accurately reflects tool usage
- [ ] Migration guide helps users transition from Chat Completions

---

**This guide will be updated as implementation progresses.**
