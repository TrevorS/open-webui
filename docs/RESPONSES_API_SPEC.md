# OpenAI Responses API - Technical Specification

**Last Updated:** January 2025
**API Version:** v1
**Status:** Production

## Table of Contents

1. [Overview](#overview)
2. [API Endpoints](#api-endpoints)
3. [Authentication](#authentication)
4. [Request Format](#request-format)
5. [Response Format](#response-format)
6. [Streaming](#streaming)
7. [Tools](#tools)
8. [Stateful Conversations](#stateful-conversations)
9. [Background Mode](#background-mode)
10. [Error Handling](#error-handling)
11. [Pricing](#pricing)
12. [Differences from Chat Completions API](#differences-from-chat-completions-api)

---

## Overview

The **OpenAI Responses API** is OpenAI's latest stateful API that combines the best features of the Chat Completions and Assistants APIs into a unified interface. Released in March 2025, it provides:

- **Optional stateful conversations** - Server-side state management via `previous_response_id`
- **Preserved reasoning state** - Model's step-by-step reasoning persists across turns
- **Built-in advanced tools** - MCP, code interpreter, file search, image generation, web search
- **Better performance** - 40-80% better cache utilization, 5% improvement on TAUBench
- **Simplified API** - Reduces hundreds of lines of code to just a few

### Key Benefits

- **Lower latency** due to improved caching
- **Lower costs** from better token utilization
- **Simpler code** with optional state management
- **More capabilities** with built-in tools
- **Better reasoning** with preserved state across turns

---

## API Endpoints

### Base URL

```
https://api.openai.com/v1
```

### Primary Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/responses` | POST | Create a new response (stateless or stateful) |
| `/v1/responses/{response_id}` | GET | Retrieve a specific response (for background mode) |

---

## Authentication

### Header Format

All requests must include a valid API key in the `Authorization` header using Bearer authentication:

```http
Authorization: Bearer YOUR_API_KEY
```

### Example with cURL

```bash
curl https://api.openai.com/v1/responses \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -d '{
    "model": "gpt-4o",
    "input": "Hello, world!"
  }'
```

### Example with Python

```python
from openai import OpenAI

client = OpenAI(api_key="YOUR_API_KEY")

response = client.responses.create(
    model="gpt-4o",
    input="Hello, world!"
)
```

---

## Request Format

### Basic Structure (Stateful Mode)

```json
{
  "model": "gpt-4o",
  "input": "What's the weather in Paris?",
  "store": true,
  "previous_response_id": "resp_xxx",
  "instructions": "You are a helpful assistant.",
  "tools": [],
  "stream": false,
  "temperature": 1.0,
  "max_output_tokens": null,
  "max_prompt_tokens": null,
  "truncation_strategy": "auto",
  "metadata": {},
  "modalities": ["text"]
}
```

### Alternative Structure (Stateless Mode)

```json
{
  "model": "gpt-4o",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "tools": [],
  "stream": false
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model` | string | **Yes** | Model ID (e.g., `gpt-4o`, `gpt-4.1-nano`, `o3`, `o4-mini`) |
| `input` | string | No* | User input for stateful mode (*Required if `messages` not provided) |
| `messages` | array | No* | Message history for stateless mode (*Required if `input` not provided) |
| `previous_response_id` | string | No | ID of previous response to continue conversation (stateful) |
| `store` | boolean | No | If true, store conversation state on OpenAI servers (default: false) |
| `instructions` | string | No | System instructions for the assistant |
| `tools` | array | No | Array of tool definitions (see [Tools](#tools) section) |
| `tool_choice` | string/object | No | Control tool selection: "auto", "required", "none", or specific tool |
| `stream` | boolean | No | Enable streaming responses (default: false) |
| `temperature` | number | No | Sampling temperature 0-2 (default: 1.0) |
| `max_output_tokens` | integer | No | Maximum tokens in the output (default: model's max) |
| `max_prompt_tokens` | integer | No | Maximum tokens from prompt/history |
| `truncation_strategy` | string | No | How to truncate history: "auto" or "last_messages" |
| `metadata` | object | No | Custom metadata attached to the response |
| `modalities` | array | No | Output modalities: ["text"], ["text", "audio"] |
| `background` | boolean | No | Run as background task (default: false) |

### Supported Models

- **GPT-4o series**: `gpt-4o`, `gpt-4o-mini`
- **GPT-4.1 series**: `gpt-4.1`, `gpt-4.1-nano`
- **O-series reasoning models**: `o3`, `o4-mini`

---

## Response Format

### Basic Response Structure

```json
{
  "id": "resp_67cb32528d6881909eb2859a55e18a85",
  "object": "response",
  "created_at": 1735948800,
  "model": "gpt-4o-2024-08-06",
  "instructions": "You are a helpful assistant.",
  "output": [
    {
      "id": "msg_abc123",
      "type": "message",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "Hello! How can I help you today?",
          "annotations": []
        }
      ],
      "status": "completed"
    }
  ],
  "output_text": "Hello! How can I help you today?",
  "status": "completed",
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 25,
    "total_tokens": 175
  },
  "metadata": {},
  "incomplete_details": null,
  "error": null
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique response identifier (starts with `resp_`) |
| `object` | string | Always "response" |
| `created_at` | integer | Unix timestamp of creation |
| `model` | string | Model used for the response |
| `instructions` | string | System instructions used |
| `output` | array | Array of message objects containing the response |
| `output_text` | string | Simplified text output (concatenated from all text content) |
| `status` | string | Response status: "queued", "in_progress", "completed", "failed" |
| `usage` | object | Token usage statistics |
| `metadata` | object | Custom metadata |
| `incomplete_details` | object | Details if response incomplete |
| `error` | object | Error details if failed |

### Output Message Structure

```json
{
  "id": "msg_abc123",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "output_text",
      "text": "Response text here",
      "annotations": []
    }
  ],
  "status": "completed"
}
```

### Usage Object

```json
{
  "prompt_tokens": 150,
  "completion_tokens": 25,
  "total_tokens": 175
}
```

---

## Streaming

### Enable Streaming

Set `stream: true` in the request:

```python
response = client.responses.create(
    model="gpt-4o",
    input="Write a story",
    stream=True
)

for event in response:
    print(event)
```

### Streaming Event Format

Unlike Chat Completions API, Responses API uses **full SSE (Server-Sent Events) protocol** with explicit event types:

```
event: response.created
data: {"id": "resp_xxx", "status": "in_progress"}

event: response.output_item.added
data: {"item_id": "msg_abc", "type": "message"}

event: response.output_text.delta
data: {"delta": {"text": "Hello"}}

event: response.output_text.delta
data: {"delta": {"text": " world"}}

event: response.output_item.done
data: {"item": {...}}

event: response.completed
data: {"id": "resp_xxx", "status": "completed", "usage": {...}}
```

### Event Types

| Event Type | Description |
|------------|-------------|
| `response.created` | Response initiated |
| `response.output_item.added` | New output item (message) started |
| `response.output_text.delta` | Incremental text content |
| `response.reasoning_summary_text.delta` | Reasoning process (for o-series models) |
| `response.output_item.done` | Output item completed |
| `response.completed` | Response fully completed |
| `response.failed` | Response failed |

### Streaming Benefits

- **Structured events** - Know exactly what type of update is happening
- **Reasoning visibility** - See model's thinking process (o-series models)
- **Better UX** - More granular progress updates
- **Tool tracking** - Separate events for tool calls and results

---

## Tools

The Responses API supports built-in hosted tools and custom function definitions.

### Tool Types

1. **MCP (Model Context Protocol)** - Connect to remote tool servers
2. **Code Interpreter** - Execute Python code in sandboxed environment
3. **File Search** - Vector-based document retrieval
4. **Image Generation** - Generate images with gpt-image-1
5. **Web Search (Preview)** - Built-in web search
6. **Custom Functions** - Your own function definitions

### MCP Tool

```json
{
  "type": "mcp",
  "server_label": "stripe-mcp",
  "server_url": "https://mcp.stripe.com",
  "require_approval": "never",
  "headers": {
    "Authorization": "Bearer sk_test_xxx"
  },
  "allowed_tools": ["create_payment", "get_customer"]
}
```

**MCP Server Examples:**
- **Stripe**: Payment operations
- **Zapier**: Access to 8,000+ third-party actions
- **Custom servers**: Build your own MCP-compliant tool server

**MCP Parameters:**
- `server_label`: Identifier for the server
- `server_url`: URL of the MCP server
- `require_approval`: "never", "always", or "once"
- `headers`: Authentication headers (optional)
- `allowed_tools`: Limit which tools from the server (optional)

### Code Interpreter Tool

```json
{
  "type": "code_interpreter",
  "container": {
    "type": "auto"
  }
}
```

**Capabilities:**
- Execute Python code in secure sandbox
- Process files (CSV, JSON, images, etc.)
- Generate data visualizations
- Iteratively write and debug code
- Enhanced visual reasoning

**Cost:** $0.03 per container

### File Search Tool

```json
{
  "type": "file_search",
  "file_ids": ["file-abc123", "file-def456"],
  "max_num_results": 10
}
```

**Parameters:**
- `file_ids`: Array of uploaded file IDs
- `max_num_results`: Maximum search results to return (default: 10)

**Cost:**
- $0.10/GB of vector storage per day
- $2.50 per 1k tool calls

### Image Generation Tool

```json
{
  "type": "image_generation",
  "model": "gpt-image-1"
}
```

**Capabilities:**
- Real-time streaming of image generation
- Multi-turn edits ("make the sky darker", etc.)
- Integrated into conversation flow

**Cost:**
- $5.00 per 1M text input tokens
- $10.00 per 1M image input tokens
- $40.00 per 1M image output tokens

### Web Search Tool (Preview)

```json
{
  "type": "web_search_preview"
}
```

**Note:** Preview feature, may change.

### Custom Function Tool

```json
{
  "type": "function",
  "function": {
    "name": "get_weather",
    "description": "Get current weather for a location",
    "parameters": {
      "type": "object",
      "properties": {
        "location": {
          "type": "string",
          "description": "City name"
        }
      },
      "required": ["location"]
    }
  }
}
```

### Tool Choice Parameter

Control when tools are used:

```json
{
  "tool_choice": "auto"  // Let model decide
}
```

```json
{
  "tool_choice": "required"  // Force tool use
}
```

```json
{
  "tool_choice": "none"  // Never use tools
}
```

```json
{
  "tool_choice": {
    "type": "function",
    "function": {"name": "get_weather"}  // Force specific tool
  }
}
```

### Example with Tools

```python
response = client.responses.create(
    model="gpt-4o",
    input="What's the weather in Paris? Also, create a chart showing temperatures.",
    tools=[
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather data",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "code_interpreter"
        }
    ],
    tool_choice="auto"
)
```

---

## Stateful Conversations

One of the most powerful features of the Responses API is optional server-side state management.

### Traditional Stateless Approach (Still Supported)

```python
# You manage the full message history
response = client.responses.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
        {"role": "user", "content": "What's the weather?"}
    ]
)
```

### New Stateful Approach

```python
# First message - create state
response1 = client.responses.create(
    model="gpt-4o",
    input="Hello",
    store=True  # Store conversation state on OpenAI servers
)

print(response1.output_text)
# "Hi! How can I help?"

# Continue conversation - just pass the response ID
response2 = client.responses.create(
    model="gpt-4o",
    input="What's the weather?",
    previous_response_id=response1.id,  # Reference previous state
    store=True
)

print(response2.output_text)
# "I'll need your location to check the weather..."
```

### Key Concepts

**`store: true`**
- Instructs OpenAI to save conversation state on their servers
- You don't need to send full message history
- State persists for a limited time (check OpenAI docs for retention period)

**`previous_response_id`**
- References the previous response in the conversation
- Continues the conversation from that point
- OpenAI loads the full context automatically

### Benefits of Stateful Mode

1. **Simpler code** - No need to track message arrays
2. **Lower bandwidth** - Don't send full history every time
3. **Better caching** - 40-80% better cache utilization
4. **Preserved reasoning** - Model's thinking process continues across turns
5. **Better performance** - 5% improvement on benchmarks

### When to Use Stateful vs Stateless

**Use Stateful When:**
- Building chat applications
- Long multi-turn conversations
- You want to minimize bandwidth
- You trust OpenAI to manage state

**Use Stateless When:**
- You need full control over conversation history
- Data privacy requires local storage
- Building custom conversation flows
- Debugging conversation issues

---

## Background Mode

For long-running tasks (especially with o-series reasoning models), background mode runs requests asynchronously.

### Enable Background Mode

```python
response = client.responses.create(
    model="o3",
    input="Write a comprehensive analysis of quantum computing",
    background=True  # Run asynchronously
)

print(response.id)
# resp_abc123
print(response.status)
# "queued"
```

### Polling for Completion

```python
import time

response_id = response.id

while True:
    response = client.responses.retrieve(response_id)

    if response.status in ["completed", "failed"]:
        break

    print(f"Status: {response.status}")
    time.sleep(2)  # Wait 2 seconds between polls

if response.status == "completed":
    print(response.output_text)
else:
    print(f"Failed: {response.error}")
```

### Response Status Values

| Status | Description |
|--------|-------------|
| `queued` | Request accepted, waiting to start |
| `in_progress` | Currently processing |
| `completed` | Successfully finished |
| `failed` | Processing failed (check `error` field) |

### Use Cases for Background Mode

- **Complex reasoning tasks** (o3, o1-pro) that take minutes
- **Large document analysis**
- **Code generation projects**
- **Research agents** like Deep Research
- **Batch processing** where immediate response not needed

### Streaming with Background Mode

**Note:** Background mode and streaming can be combined, but be aware of potential performance issues (being addressed by OpenAI).

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "message": "Invalid API key provided",
    "type": "invalid_request_error",
    "param": null,
    "code": "invalid_api_key"
  }
}
```

### Common Error Types

| HTTP Status | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_request_error` | Bad request (missing required params, invalid format) |
| 401 | `authentication_error` | Invalid or missing API key |
| 403 | `permission_denied_error` | API key doesn't have required permissions |
| 404 | `not_found_error` | Resource (model, response_id) not found |
| 422 | `unprocessable_entity_error` | Valid format but semantic errors |
| 429 | `rate_limit_error` | Too many requests (rate limit exceeded) |
| 500 | `api_error` | Internal server error |
| 503 | `service_unavailable_error` | Service temporarily unavailable |

### Error Handling Best Practices

```python
from openai import OpenAI, APIError, RateLimitError, APIConnectionError
import time

client = OpenAI()

def create_response_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.responses.create(
                model="gpt-4o",
                input="Hello"
            )
            return response

        except RateLimitError as e:
            # Exponential backoff for rate limits
            wait_time = 2 ** attempt
            print(f"Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)

        except APIConnectionError as e:
            # Network issues - retry with backoff
            wait_time = 2 ** attempt
            print(f"Connection error. Retrying in {wait_time}s...")
            time.sleep(wait_time)

        except APIError as e:
            # Server error (5xx) - may be transient
            if e.status_code >= 500:
                wait_time = 2 ** attempt
                print(f"Server error. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                # Client error (4xx) - don't retry
                raise

    raise Exception("Max retries exceeded")
```

### Retry Guidelines

**Retry these errors:**
- Rate limits (429) - use exponential backoff
- Server errors (500-503) - temporary issues
- Network timeouts - connection issues

**Don't retry these errors:**
- Authentication errors (401) - won't resolve without fixing API key
- Invalid requests (400) - code changes required
- Not found (404) - resource doesn't exist

---

## Pricing

### Base Model Costs

Standard OpenAI model pricing applies (per 1M tokens):
- **GPT-4o**: $2.50 input / $10.00 output
- **GPT-4o-mini**: $0.15 input / $0.60 output
- **GPT-4.1**: Varies by model
- **o3**: Varies by reasoning budget

### Tool Costs (Additional)

| Tool | Cost |
|------|------|
| MCP Server | No additional cost (just token costs) |
| Code Interpreter | $0.03 per container |
| File Search | $0.10/GB/day storage + $2.50/1k calls |
| Image Generation | $5.00/1M text tokens, $10.00/1M image input, $40.00/1M image output |
| Web Search | Included in model costs |

### Cost Savings with Stateful Mode

- **40-80% better cache utilization** reduces repeated processing
- **Lower bandwidth** saves on prompt tokens (no full history resent)
- **Preserved reasoning** may reduce total turns needed

### Example Cost Calculation

```
Conversation with 10 turns, each 100 tokens prompt + 50 tokens response:

Stateless (Chat Completions):
- Turn 1: 100 input + 50 output = 150 tokens
- Turn 2: 150 input + 50 output = 200 tokens
- Turn 10: 550 input + 50 output = 600 tokens
Total: ~3,250 input tokens + 500 output tokens

Stateful (Responses API):
- Each turn: ~100 input + 50 output = 150 tokens
Total: ~1,000 input tokens + 500 output tokens

Savings: ~70% reduction in input tokens
```

---

## Differences from Chat Completions API

### High-Level Comparison

| Feature | Chat Completions API | Responses API |
|---------|---------------------|---------------|
| **Endpoint** | `/v1/chat/completions` | `/v1/responses` |
| **State Management** | Client-side (stateless) | Optional server-side (stateful) |
| **Message History** | Send full history each time | Use `previous_response_id` |
| **Built-in Tools** | Function calling only | MCP, code interpreter, file search, image gen, web search |
| **Streaming Format** | `data:` only | Full SSE with `event:` + `data:` |
| **Reasoning State** | Lost between turns | Preserved across turns |
| **Cache Efficiency** | Baseline | 40-80% better |
| **Background Tasks** | Not supported | Supported with polling |

### API Migration Examples

#### Chat Completions (Old)

```python
from openai import OpenAI
client = OpenAI()

# Maintain conversation history manually
messages = []

# Turn 1
messages.append({"role": "user", "content": "Hello"})
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages
)
messages.append({"role": "assistant", "content": response.choices[0].message.content})

# Turn 2 - must send full history
messages.append({"role": "user", "content": "Tell me a joke"})
response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages  # Full history sent again
)
```

#### Responses API (New - Stateful)

```python
from openai import OpenAI
client = OpenAI()

# Turn 1
response1 = client.responses.create(
    model="gpt-4o",
    input="Hello",
    store=True
)

# Turn 2 - just reference previous response
response2 = client.responses.create(
    model="gpt-4o",
    input="Tell me a joke",
    previous_response_id=response1.id,
    store=True
)
```

#### Responses API (New - Stateless)

```python
# Can still use messages if you prefer
response = client.responses.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
        {"role": "user", "content": "Tell me a joke"}
    ]
)
```

### Streaming Differences

#### Chat Completions Streaming

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

**Stream format:**
```
data: {"choices":[{"delta":{"content":"Hello"}}]}
data: {"choices":[{"delta":{"content":" world"}}]}
data: [DONE]
```

#### Responses API Streaming

```python
response = client.responses.create(
    model="gpt-4o",
    input="Hello",
    stream=True
)

for event in response:
    if event.type == "response.output_text.delta":
        print(event.data.delta.text, end="")
```

**Stream format:**
```
event: response.created
data: {"id":"resp_xxx","status":"in_progress"}

event: response.output_text.delta
data: {"delta":{"text":"Hello"}}

event: response.output_text.delta
data: {"delta":{"text":" world"}}

event: response.completed
data: {"id":"resp_xxx","status":"completed"}
```

### Tool Calling Differences

#### Chat Completions - Custom Functions Only

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "What's the weather?"}],
    tools=[{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather",
            "parameters": {...}
        }
    }]
)
```

#### Responses API - Built-in + Custom

```python
response = client.responses.create(
    model="gpt-4o",
    input="What's the weather? Also run this code: print('hello')",
    tools=[
        {"type": "web_search_preview"},  # Built-in
        {"type": "code_interpreter"},     # Built-in
        {                                 # Custom
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {...}
            }
        }
    ]
)
```

---

## Implementation Checklist

When implementing Responses API support in Open WebUI:

### Backend Tasks

- [ ] Create `/responses` router
- [ ] Add `ENABLE_RESPONSES_API` configuration
- [ ] Implement stateful conversation support
- [ ] Add database table for response tracking
- [ ] Implement format conversion (Responses ↔ Chat Completions)
- [ ] Add streaming event parsing
- [ ] Implement background mode polling
- [ ] Add tool support:
  - [ ] MCP server configuration
  - [ ] Code interpreter
  - [ ] File search
  - [ ] Image generation
  - [ ] Web search
- [ ] Add cost tracking for tools
- [ ] Implement error handling with retries
- [ ] Add request/response logging

### Frontend Tasks

- [ ] Create Responses API client functions
- [ ] Add admin UI for configuration
- [ ] Add toggle for stateful/stateless mode
- [ ] Implement `previous_response_id` tracking
- [ ] Add tool selection UI
- [ ] Create tool result display components:
  - [ ] Code execution results
  - [ ] Web search results
  - [ ] Generated images
  - [ ] File search results
- [ ] Add background task status polling
- [ ] Update streaming handler for new event types
- [ ] Add cost/usage display for tools

### Testing Tasks

- [ ] Unit tests for format conversion
- [ ] Integration tests for each tool type
- [ ] End-to-end stateful conversation test
- [ ] Background mode polling test
- [ ] Streaming event parsing test
- [ ] Error handling test suite
- [ ] Performance benchmarks (cache utilization)

---

## Additional Resources

- **Official Docs:** https://platform.openai.com/docs/api-reference/responses
- **Migration Guide:** https://platform.openai.com/docs/guides/migrate-to-responses
- **MCP Specification:** https://spec.modelcontextprotocol.io/
- **OpenAI Cookbook:** https://cookbook.openai.com/
- **Community Forum:** https://community.openai.com/

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2025-03 | 1.0 | Initial Responses API release |
| 2025-05 | 1.1 | Added MCP, image generation, code interpreter |
| 2025-06 | 1.2 | Background mode improvements |

---

**Document prepared for Open WebUI integration planning**
