# OpenAI Responses API - Native First-Class Implementation

**Philosophy:** Responses API as the PRIMARY interface, not a wrapper or compatibility layer.

**Goal:** Expose all Responses API features natively in Open WebUI:
- Stateful conversations with preserved reasoning
- Native tool support (MCP, Code Interpreter, File Search, Image Gen, Web Search)
- Background mode for long-running tasks
- Proper streaming with typed events
- Cost tracking per tool
- Tool result visualizations

---

## Table of Contents

1. [Architectural Vision](#architectural-vision)
2. [Database Schema (Response-First)](#database-schema-response-first)
3. [Backend Architecture](#backend-architecture)
4. [Frontend Architecture](#frontend-architecture)
5. [Tool System](#tool-system)
6. [Implementation Roadmap](#implementation-roadmap)

---

## Architectural Vision

### Current Architecture (Message-Based)

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌─────────────────┐
│  User   │────▶│Frontend │────▶│ Backend  │────▶│ Chat Completions│
│         │     │         │     │          │     │      API        │
└─────────┘     └─────────┘     └──────────┘     └─────────────────┘
                     │                │
                     │                │
                     ▼                ▼
                ┌─────────────────────────┐
                │   Database (Messages)   │
                │  - Full history stored  │
                │  - Sent every request   │
                └─────────────────────────┘
```

### New Architecture (Response-First)

```
┌─────────┐     ┌──────────────┐     ┌──────────┐     ┌─────────────┐
│  User   │────▶│  Frontend    │────▶│ Backend  │────▶│  Responses  │
│         │     │  (Native     │     │ (Native  │     │     API     │
│         │     │   Response   │     │ Response │     │             │
│         │     │   Format)    │     │ Format)  │     └─────────────┘
└─────────┘     └──────────────┘     └──────────┘
                     │                     │
                     │                     ▼
                     │            ┌─────────────────┐
                     │            │  Response Store │
                     │            │  - response_ids │
                     │            │  - tool_calls   │
                     │            │  - artifacts    │
                     │            └─────────────────┘
                     │
                     ▼
            ┌────────────────────────────┐
            │    Rich UI Components      │
            ├────────────────────────────┤
            │ • Reasoning Traces         │
            │ • Code Execution Results   │
            │ • Generated Images         │
            │ • Web Search Results       │
            │ • File Search Snippets     │
            │ • MCP Tool Outputs         │
            └────────────────────────────┘
```

### Key Principles

1. **Response Objects are Primary** - Not messages, but full Response objects with tools, artifacts, reasoning
2. **Stateful by Default** - Leverage OpenAI's server-side state management
3. **Tool-Native UI** - Each tool type has dedicated UI components
4. **Event-Driven Streaming** - Proper SSE event handling with typed events
5. **Background Tasks** - Support long-running reasoning with polling
6. **Cost Transparency** - Track and display per-tool costs
7. **Artifact Management** - Images, files, code outputs stored and displayed

---

## Database Schema (Response-First)

### Core Tables

#### 1. Responses Table (Primary)

```sql
CREATE TABLE responses (
    -- Identity
    id VARCHAR PRIMARY KEY,              -- OpenAI response_id (resp_xxx)
    chat_id VARCHAR NOT NULL,            -- References chats table
    user_id VARCHAR NOT NULL,

    -- Response metadata
    model VARCHAR NOT NULL,
    created_at BIGINT NOT NULL,          -- Unix timestamp
    status VARCHAR NOT NULL,             -- queued, in_progress, completed, failed

    -- Conversation chain
    previous_response_id VARCHAR,        -- Links to previous response
    next_response_id VARCHAR,            -- Links to next response (for traversal)
    conversation_position INTEGER,       -- Position in conversation

    -- Content
    instructions TEXT,                   -- System instructions used
    input_text TEXT,                     -- User input (for stateful mode)
    output_text TEXT,                    -- Assistant output (flattened)
    output_items JSONB,                  -- Full output array from API

    -- Reasoning (for o-series models)
    reasoning_summary TEXT,              -- Model's reasoning process
    reasoning_tokens INTEGER,            -- Tokens used for reasoning

    -- State management
    is_stored_on_openai BOOLEAN DEFAULT FALSE,  -- Using OpenAI's state storage

    -- Token usage
    usage_prompt_tokens INTEGER,
    usage_completion_tokens INTEGER,
    usage_total_tokens INTEGER,

    -- Cost tracking
    base_cost DECIMAL(10, 6),           -- Base model cost
    tool_costs JSONB,                    -- Per-tool cost breakdown
    total_cost DECIMAL(10, 6),          -- Total cost for this response

    -- Metadata
    metadata JSONB,
    error JSONB,

    -- Indexes
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (previous_response_id) REFERENCES responses(id),
    INDEX idx_chat_id (chat_id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_conversation_position (conversation_position)
);
```

#### 2. Tool Calls Table

```sql
CREATE TABLE tool_calls (
    -- Identity
    id VARCHAR PRIMARY KEY,              -- Tool call ID
    response_id VARCHAR NOT NULL,        -- Parent response

    -- Tool information
    tool_type VARCHAR NOT NULL,          -- mcp, code_interpreter, file_search, etc.
    tool_name VARCHAR,                   -- For MCP/function tools

    -- Execution
    status VARCHAR NOT NULL,             -- queued, running, completed, failed
    created_at BIGINT NOT NULL,
    completed_at BIGINT,

    -- Input/Output
    input_parameters JSONB,              -- Tool input
    output_data JSONB,                   -- Tool output
    error JSONB,                         -- Error if failed

    -- MCP specific
    mcp_server_label VARCHAR,            -- Which MCP server
    mcp_server_url VARCHAR,

    -- Code Interpreter specific
    code_content TEXT,                   -- Python code executed
    code_output TEXT,                    -- Execution output
    container_id VARCHAR,                -- Container used

    -- File Search specific
    file_ids JSONB,                      -- Files searched
    search_results JSONB,                -- Search results with citations

    -- Image Generation specific
    image_prompt TEXT,                   -- Generation prompt
    image_urls JSONB,                    -- Generated image URLs

    -- Cost tracking
    cost DECIMAL(10, 6),                 -- Cost for this tool call

    -- Metadata
    metadata JSONB,

    FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE,
    INDEX idx_response_id (response_id),
    INDEX idx_tool_type (tool_type),
    INDEX idx_status (status)
);
```

#### 3. Artifacts Table

```sql
CREATE TABLE artifacts (
    -- Identity
    id VARCHAR PRIMARY KEY,
    response_id VARCHAR NOT NULL,
    tool_call_id VARCHAR,               -- Optional: which tool created it

    -- Artifact information
    type VARCHAR NOT NULL,              -- image, file, code_output, chart, etc.
    name VARCHAR,
    mime_type VARCHAR,

    -- Storage
    storage_type VARCHAR NOT NULL,      -- local, s3, openai_url
    storage_path TEXT,                  -- Path or URL
    size_bytes BIGINT,

    -- Content (for small artifacts)
    content_text TEXT,                  -- For text-based artifacts
    content_data BYTEA,                 -- For binary artifacts (small files)

    -- Metadata
    created_at BIGINT NOT NULL,
    expires_at BIGINT,                  -- For temporary artifacts
    metadata JSONB,

    FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE,
    FOREIGN KEY (tool_call_id) REFERENCES tool_calls(id),
    INDEX idx_response_id (response_id),
    INDEX idx_type (type)
);
```

#### 4. Updated Chats Table

```sql
ALTER TABLE chats ADD COLUMN IF NOT EXISTS
    uses_responses_api BOOLEAN DEFAULT TRUE,        -- Using Responses API
    current_response_id VARCHAR,                     -- Latest response in chain
    conversation_length INTEGER DEFAULT 0,           -- Number of responses
    total_cost DECIMAL(10, 6) DEFAULT 0,            -- Cumulative cost
    enabled_tools JSONB,                             -- Which tools are enabled
    mcp_servers JSONB;                               -- MCP server configs for this chat

ALTER TABLE chats ADD CONSTRAINT fk_current_response
    FOREIGN KEY (current_response_id) REFERENCES responses(id);
```

### Migration Strategy

```python
# backend/open_webui/migrations/add_responses_api_tables.py

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create responses table
    op.create_table(
        'responses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('previous_response_id', sa.String(), nullable=True),
        sa.Column('next_response_id', sa.String(), nullable=True),
        sa.Column('conversation_position', sa.Integer(), nullable=True),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('input_text', sa.Text(), nullable=True),
        sa.Column('output_text', sa.Text(), nullable=True),
        sa.Column('output_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reasoning_summary', sa.Text(), nullable=True),
        sa.Column('reasoning_tokens', sa.Integer(), nullable=True),
        sa.Column('is_stored_on_openai', sa.Boolean(), default=False),
        sa.Column('usage_prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('usage_completion_tokens', sa.Integer(), nullable=True),
        sa.Column('usage_total_tokens', sa.Integer(), nullable=True),
        sa.Column('base_cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('tool_costs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('total_cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['previous_response_id'], ['responses.id'])
    )

    # Create indexes
    op.create_index('idx_responses_chat_id', 'responses', ['chat_id'])
    op.create_index('idx_responses_user_id', 'responses', ['user_id'])
    op.create_index('idx_responses_created_at', 'responses', ['created_at'])

    # Create tool_calls table
    op.create_table(
        'tool_calls',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('response_id', sa.String(), nullable=False),
        sa.Column('tool_type', sa.String(), nullable=False),
        sa.Column('tool_name', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('completed_at', sa.BigInteger(), nullable=True),
        sa.Column('input_parameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('mcp_server_label', sa.String(), nullable=True),
        sa.Column('mcp_server_url', sa.String(), nullable=True),
        sa.Column('code_content', sa.Text(), nullable=True),
        sa.Column('code_output', sa.Text(), nullable=True),
        sa.Column('container_id', sa.String(), nullable=True),
        sa.Column('file_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('search_results', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('image_prompt', sa.Text(), nullable=True),
        sa.Column('image_urls', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('cost', sa.Numeric(10, 6), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE')
    )

    op.create_index('idx_tool_calls_response_id', 'tool_calls', ['response_id'])
    op.create_index('idx_tool_calls_tool_type', 'tool_calls', ['tool_type'])

    # Create artifacts table
    op.create_table(
        'artifacts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('response_id', sa.String(), nullable=False),
        sa.Column('tool_call_id', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('mime_type', sa.String(), nullable=True),
        sa.Column('storage_type', sa.String(), nullable=False),
        sa.Column('storage_path', sa.Text(), nullable=True),
        sa.Column('size_bytes', sa.BigInteger(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('content_data', sa.LargeBinary(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_call_id'], ['tool_calls.id'])
    )

    op.create_index('idx_artifacts_response_id', 'artifacts', ['response_id'])
    op.create_index('idx_artifacts_type', 'artifacts', ['type'])

    # Update chats table
    op.add_column('chats', sa.Column('uses_responses_api', sa.Boolean(), default=True))
    op.add_column('chats', sa.Column('current_response_id', sa.String(), nullable=True))
    op.add_column('chats', sa.Column('conversation_length', sa.Integer(), default=0))
    op.add_column('chats', sa.Column('total_cost', sa.Numeric(10, 6), default=0))
    op.add_column('chats', sa.Column('enabled_tools', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('chats', sa.Column('mcp_servers', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key('fk_current_response', 'chats', 'responses', ['current_response_id'], ['id'])

def downgrade():
    op.drop_table('artifacts')
    op.drop_table('tool_calls')
    op.drop_table('responses')
    op.drop_constraint('fk_current_response', 'chats')
    op.drop_column('chats', 'uses_responses_api')
    op.drop_column('chats', 'current_response_id')
    op.drop_column('chats', 'conversation_length')
    op.drop_column('chats', 'total_cost')
    op.drop_column('chats', 'enabled_tools')
    op.drop_column('chats', 'mcp_servers')
```

---

## Backend Architecture

### Project Structure

```
backend/open_webui/
├── models/
│   ├── responses.py          # Response, ToolCall, Artifact models
│   └── chats.py              # Updated Chat model
├── routers/
│   ├── responses.py          # Main Responses API router
│   ├── tools.py              # Tool management router
│   └── artifacts.py          # Artifact retrieval router
├── services/
│   ├── responses_service.py  # Business logic for responses
│   ├── tools/
│   │   ├── mcp_service.py
│   │   ├── code_interpreter_service.py
│   │   ├── file_search_service.py
│   │   ├── image_gen_service.py
│   │   └── web_search_service.py
│   └── cost_calculator.py    # Cost tracking
└── utils/
    ├── streaming.py          # SSE event parsing
    └── background_tasks.py   # Background mode polling
```

### Core Models

**File:** `/backend/open_webui/models/responses.py`

```python
from sqlalchemy import Column, String, Integer, Text, Boolean, DECIMAL, ForeignKey, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from open_webui.internal.db import Base
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class Response(Base):
    """
    Native OpenAI Response object.

    Represents a single response in a conversation chain.
    Can contain tool calls, artifacts, and reasoning traces.
    """
    __tablename__ = "responses"

    # Identity
    id = Column(String, primary_key=True)
    chat_id = Column(String, ForeignKey("chat.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("user.id"), nullable=False)

    # Response metadata
    model = Column(String, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False)  # queued, in_progress, completed, failed

    # Conversation chain
    previous_response_id = Column(String, ForeignKey("responses.id"))
    next_response_id = Column(String)
    conversation_position = Column(Integer)

    # Content
    instructions = Column(Text)
    input_text = Column(Text)
    output_text = Column(Text)
    output_items = Column(JSONB)

    # Reasoning
    reasoning_summary = Column(Text)
    reasoning_tokens = Column(Integer)

    # State
    is_stored_on_openai = Column(Boolean, default=False)

    # Usage
    usage_prompt_tokens = Column(Integer)
    usage_completion_tokens = Column(Integer)
    usage_total_tokens = Column(Integer)

    # Cost
    base_cost = Column(DECIMAL(10, 6))
    tool_costs = Column(JSONB)
    total_cost = Column(DECIMAL(10, 6))

    # Metadata
    metadata = Column(JSONB)
    error = Column(JSONB)

    # Relationships
    chat = relationship("Chat", back_populates="responses")
    user = relationship("User")
    tool_calls = relationship("ToolCall", back_populates="response", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="response", cascade="all, delete-orphan")
    previous_response = relationship("Response", remote_side=[id], foreign_keys=[previous_response_id])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching OpenAI Response format"""
        return {
            "id": self.id,
            "object": "response",
            "created_at": self.created_at,
            "model": self.model,
            "status": self.status,
            "instructions": self.instructions,
            "output": self.output_items or [],
            "output_text": self.output_text,
            "usage": {
                "prompt_tokens": self.usage_prompt_tokens or 0,
                "completion_tokens": self.usage_completion_tokens or 0,
                "total_tokens": self.usage_total_tokens or 0,
            } if self.usage_total_tokens else None,
            "metadata": self.metadata or {},
            "error": self.error,
            # Extensions for UI
            "_tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "_artifacts": [a.to_dict() for a in self.artifacts],
            "_reasoning_summary": self.reasoning_summary,
            "_costs": {
                "base": float(self.base_cost) if self.base_cost else 0,
                "tools": self.tool_costs or {},
                "total": float(self.total_cost) if self.total_cost else 0,
            }
        }


class ToolCall(Base):
    """
    Represents a tool call within a response.

    Stores tool type, input, output, and execution metadata.
    """
    __tablename__ = "tool_calls"

    id = Column(String, primary_key=True)
    response_id = Column(String, ForeignKey("responses.id", ondelete="CASCADE"), nullable=False)

    # Tool info
    tool_type = Column(String, nullable=False)
    tool_name = Column(String)

    # Execution
    status = Column(String, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    completed_at = Column(BigInteger)

    # I/O
    input_parameters = Column(JSONB)
    output_data = Column(JSONB)
    error = Column(JSONB)

    # MCP specific
    mcp_server_label = Column(String)
    mcp_server_url = Column(String)

    # Code Interpreter specific
    code_content = Column(Text)
    code_output = Column(Text)
    container_id = Column(String)

    # File Search specific
    file_ids = Column(JSONB)
    search_results = Column(JSONB)

    # Image Generation specific
    image_prompt = Column(Text)
    image_urls = Column(JSONB)

    # Cost
    cost = Column(DECIMAL(10, 6))

    # Metadata
    metadata = Column(JSONB)

    # Relationships
    response = relationship("Response", back_populates="tool_calls")
    artifacts = relationship("Artifact", back_populates="tool_call", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = {
            "id": self.id,
            "type": self.tool_type,
            "name": self.tool_name,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "input": self.input_parameters,
            "output": self.output_data,
            "error": self.error,
            "cost": float(self.cost) if self.cost else 0,
        }

        # Add type-specific fields
        if self.tool_type == "code_interpreter":
            result["code"] = self.code_content
            result["execution_output"] = self.code_output
            result["container_id"] = self.container_id
        elif self.tool_type == "file_search":
            result["file_ids"] = self.file_ids
            result["results"] = self.search_results
        elif self.tool_type == "image_generation":
            result["prompt"] = self.image_prompt
            result["images"] = self.image_urls
        elif self.tool_type == "mcp":
            result["server"] = {
                "label": self.mcp_server_label,
                "url": self.mcp_server_url
            }

        return result


class Artifact(Base):
    """
    Represents an artifact created by a response or tool.

    Can be images, files, charts, code outputs, etc.
    """
    __tablename__ = "artifacts"

    id = Column(String, primary_key=True)
    response_id = Column(String, ForeignKey("responses.id", ondelete="CASCADE"), nullable=False)
    tool_call_id = Column(String, ForeignKey("tool_calls.id"))

    # Artifact info
    type = Column(String, nullable=False)  # image, file, code_output, chart, etc.
    name = Column(String)
    mime_type = Column(String)

    # Storage
    storage_type = Column(String, nullable=False)  # local, s3, openai_url
    storage_path = Column(Text)
    size_bytes = Column(BigInteger)

    # Content
    content_text = Column(Text)
    content_data = Column(String)  # Base64 encoded for small files

    # Metadata
    created_at = Column(BigInteger, nullable=False)
    expires_at = Column(BigInteger)
    metadata = Column(JSONB)

    # Relationships
    response = relationship("Response", back_populates="artifacts")
    tool_call = relationship("ToolCall", back_populates="artifacts")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "url": f"/api/artifacts/{self.id}",  # Download URL
            "preview_url": f"/api/artifacts/{self.id}/preview" if self.type == "image" else None,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata or {}
        }


# Pydantic models for API

class ResponseCreate(BaseModel):
    """Request to create a new response"""
    model: str
    input: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    previous_response_id: Optional[str] = None
    store: bool = True
    instructions: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[str | Dict[str, Any]] = "auto"
    stream: bool = False
    temperature: Optional[float] = 1.0
    max_output_tokens: Optional[int] = None
    background: bool = False
    metadata: Optional[Dict[str, Any]] = None


class ResponseRetrieve(BaseModel):
    """Response retrieval result"""
    id: str
    object: str = "response"
    created_at: int
    model: str
    status: str
    output: List[Dict[str, Any]]
    output_text: Optional[str]
    usage: Optional[Dict[str, int]]
    tool_calls: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = []
    reasoning_summary: Optional[str]
    costs: Dict[str, Any]
    metadata: Dict[str, Any]
```

### Response Service

**File:** `/backend/open_webui/services/responses_service.py`

```python
"""
Business logic for Responses API integration.

Handles:
- Creating responses
- Managing stateful conversations
- Tool orchestration
- Cost calculation
- Artifact management
"""

from openai import AsyncOpenAI
from typing import Optional, Dict, Any, List
import logging
import time
from decimal import Decimal

from open_webui.models.responses import Response, ToolCall, Artifact, ResponseCreate
from open_webui.services.cost_calculator import calculate_response_cost
from open_webui.config import OPENAI_API_KEY, OPENAI_API_BASE_URL

log = logging.getLogger(__name__)


class ResponsesService:
    """Service for managing OpenAI Responses API"""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.client = AsyncOpenAI(
            api_key=api_key or OPENAI_API_KEY,
            base_url=base_url or OPENAI_API_BASE_URL
        )

    async def create_response(
        self,
        chat_id: str,
        user_id: str,
        request: ResponseCreate
    ) -> Response:
        """
        Create a new response using OpenAI Responses API.

        Stores the full response object in database including
        tool calls and artifacts.
        """
        # Build request payload
        payload = {
            "model": request.model,
        }

        # Stateful or stateless mode
        if request.input and request.previous_response_id:
            # Continuing stateful conversation
            payload["input"] = request.input
            payload["previous_response_id"] = request.previous_response_id
            payload["store"] = request.store
        elif request.input:
            # First message in stateful conversation
            payload["input"] = request.input
            payload["store"] = request.store
        elif request.messages:
            # Stateless mode with full history
            payload["messages"] = request.messages
        else:
            raise ValueError("Must provide either 'input' or 'messages'")

        # Add optional parameters
        if request.instructions:
            payload["instructions"] = request.instructions
        if request.tools:
            payload["tools"] = request.tools
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_output_tokens:
            payload["max_output_tokens"] = request.max_output_tokens
        if request.background:
            payload["background"] = request.background
        if request.metadata:
            payload["metadata"] = request.metadata

        payload["stream"] = request.stream

        # Call OpenAI Responses API
        try:
            openai_response = await self.client.responses.create(**payload)

            # Parse and store response
            response = await self._store_response(
                openai_response=openai_response,
                chat_id=chat_id,
                user_id=user_id,
                request=request
            )

            return response

        except Exception as e:
            log.exception(f"Failed to create response: {e}")
            raise

    async def _store_response(
        self,
        openai_response: Any,
        chat_id: str,
        user_id: str,
        request: ResponseCreate
    ) -> Response:
        """Store OpenAI response in database"""

        # Calculate position in conversation
        position = 0
        if request.previous_response_id:
            prev_response = Response.query.filter_by(id=request.previous_response_id).first()
            if prev_response:
                position = prev_response.conversation_position + 1

        # Calculate costs
        cost_info = calculate_response_cost(
            model=request.model,
            usage=openai_response.usage if hasattr(openai_response, 'usage') else None,
            tool_calls=[]  # Will be populated below
        )

        # Create response record
        response = Response(
            id=openai_response.id,
            chat_id=chat_id,
            user_id=user_id,
            model=openai_response.model,
            created_at=openai_response.created_at or int(time.time()),
            status=openai_response.status,
            previous_response_id=request.previous_response_id,
            conversation_position=position,
            instructions=request.instructions,
            input_text=request.input,
            output_text=getattr(openai_response, 'output_text', None),
            output_items=getattr(openai_response, 'output', []),
            is_stored_on_openai=request.store,
            usage_prompt_tokens=openai_response.usage.prompt_tokens if hasattr(openai_response, 'usage') else None,
            usage_completion_tokens=openai_response.usage.completion_tokens if hasattr(openai_response, 'usage') else None,
            usage_total_tokens=openai_response.usage.total_tokens if hasattr(openai_response, 'usage') else None,
            base_cost=Decimal(str(cost_info['base_cost'])),
            tool_costs=cost_info['tool_costs'],
            total_cost=Decimal(str(cost_info['total_cost'])),
            metadata=request.metadata or {}
        )

        # Save response
        # response.save()  # Implement based on your ORM

        # Parse and store tool calls if any
        # This would be done by parsing openai_response.output for tool_use items

        return response

    async def retrieve_response(self, response_id: str) -> Response:
        """Retrieve a response by ID (for background mode polling)"""
        # First check local database
        response = Response.query.filter_by(id=response_id).first()

        if response and response.status in ["completed", "failed"]:
            return response

        # Poll OpenAI API for updated status
        try:
            openai_response = await self.client.responses.retrieve(response_id)

            if response:
                # Update existing record
                response.status = openai_response.status
                response.output_text = getattr(openai_response, 'output_text', None)
                response.output_items = getattr(openai_response, 'output', [])
                # Update usage, costs, etc.
                # response.save()
            else:
                # Response not in database yet, create it
                # This shouldn't happen in normal flow
                log.warning(f"Response {response_id} not found in database")

            return response

        except Exception as e:
            log.exception(f"Failed to retrieve response: {e}")
            raise

    async def get_conversation_chain(self, chat_id: str) -> List[Response]:
        """Get full conversation chain for a chat"""
        responses = (
            Response.query
            .filter_by(chat_id=chat_id)
            .order_by(Response.conversation_position)
            .all()
        )
        return responses
```

---

## Frontend Architecture

### Component Structure

```
src/lib/
├── apis/
│   ├── responses/
│   │   ├── index.ts          # Responses API client
│   │   ├── streaming.ts      # SSE event handling
│   │   └── background.ts     # Background mode polling
│   └── tools/
│       ├── mcp.ts
│       ├── code_interpreter.ts
│       ├── file_search.ts
│       └── image_generation.ts
├── components/
│   ├── chat/
│   │   ├── Response.svelte              # Main response component
│   │   ├── ResponseHeader.svelte        # Model, timestamp, cost
│   │   ├── ResponseContent.svelte       # Main text output
│   │   ├── ResponseReasoning.svelte     # Reasoning trace (collapsible)
│   │   └── ResponseTools.svelte         # Tool calls container
│   ├── tools/
│   │   ├── ToolCall.svelte              # Generic tool call wrapper
│   │   ├── MCPToolResult.svelte
│   │   ├── CodeExecutionResult.svelte
│   │   ├── FileSearchResult.svelte
│   │   ├── ImageGenerationResult.svelte
│   │   └── WebSearchResult.svelte
│   ├── artifacts/
│   │   ├── ArtifactGallery.svelte
│   │   ├── ImageArtifact.svelte
│   │   ├── FileArtifact.svelte
│   │   └── ChartArtifact.svelte
│   └── admin/
│       ├── ResponsesAPISettings.svelte
│       ├── ToolsConfiguration.svelte
│       └── MCPServersManagement.svelte
└── stores/
    ├── responses.ts          # Response state management
    ├── tools.ts              # Tool configuration
    └── artifacts.ts          # Artifact management
```

### Response Display Component

**File:** `/src/lib/components/chat/Response.svelte`

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import ResponseHeader from './ResponseHeader.svelte';
    import ResponseContent from './ResponseContent.svelte';
    import ResponseReasoning from './ResponseReasoning.svelte';
    import ResponseTools from './ResponseTools.svelte';
    import ArtifactGallery from '../artifacts/ArtifactGallery.svelte';

    export let response: {
        id: string;
        model: string;
        created_at: number;
        status: string;
        output_text: string;
        tool_calls: any[];
        artifacts: any[];
        reasoning_summary?: string;
        costs: {
            base: number;
            tools: Record<string, number>;
            total: number;
        };
    };

    let showReasoning = false;
    let showTools = true;
    let showArtifacts = true;

    $: hasReasoning = !!response.reasoning_summary;
    $: hasTools = response.tool_calls && response.tool_calls.length > 0;
    $: hasArtifacts = response.artifacts && response.artifacts.length > 0;
</script>

<div class="response-container" data-response-id={response.id}>
    <!-- Header: Model, timestamp, cost -->
    <ResponseHeader {response} />

    <!-- Main content -->
    <ResponseContent content={response.output_text} status={response.status} />

    <!-- Reasoning trace (collapsible) -->
    {#if hasReasoning}
        <ResponseReasoning
            summary={response.reasoning_summary}
            bind:expanded={showReasoning}
        />
    {/if}

    <!-- Tool calls -->
    {#if hasTools}
        <ResponseTools
            toolCalls={response.tool_calls}
            bind:expanded={showTools}
        />
    {/if}

    <!-- Artifacts (images, files, charts) -->
    {#if hasArtifacts}
        <ArtifactGallery
            artifacts={response.artifacts}
            bind:expanded={showArtifacts}
        />
    {/if}
</div>

<style>
    .response-container {
        @apply flex flex-col gap-3 p-4 rounded-lg bg-white dark:bg-gray-800 shadow-sm;
    }
</style>
```

**(Continued in next message due to length...)**
