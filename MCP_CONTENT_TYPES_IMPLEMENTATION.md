# MCP Content Types Implementation Guide

This document describes the comprehensive implementation of MCP (Model Context Protocol) content type support in Open WebUI, including text, images, audio, resources, structured content, and progress reporting.

## Overview

The MCP specification defines rich content types that tools can return, but the current Open WebUI implementation only extracts raw content as plain text. This implementation adds full support for:

1. **Content Type Differentiation** - Text, Image, Audio, Embedded Resources
2. **Structured Content** - Type-safe JSON responses with schemas
3. **Progress Reporting** - Real-time progress updates for long-running tools
4. **Annotations** - Priority, audience targeting, and metadata
5. **Media Handling** - Automatic processing and display of images and audio

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Tool Server                         │
│  Returns: CallToolResult with content blocks, progress      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              EnhancedMCPClient                               │
│  - Connects to MCP server                                   │
│  - Sends progressToken                                       │
│  - Receives CallToolResult                                   │
│  - Listens for progress notifications                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              MCPContentParser                                │
│  - Parses CallToolResult                                     │
│  - Creates typed content blocks                              │
│  - Extracts structured content                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Middleware Integration                             │
│  - Processes content blocks                                  │
│  - Uploads images/audio to storage                           │
│  - Emits events to frontend                                  │
│  - Formats for LLM consumption                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Frontend UI                               │
│  - Displays images inline                                    │
│  - Plays audio                                               │
│  - Shows progress bars                                       │
│  - Renders structured data                                   │
└─────────────────────────────────────────────────────────────┘
```

## Content Types

### 1. TextContent

**MCP Structure:**
```python
{
    "type": "text",
    "text": "The actual text content",
    "annotations": {
        "audience": ["user"],  # or ["assistant"] or ["user", "assistant"]
        "priority": 0.8
    }
}
```

**Processing:**
- Concatenated into tool result string
- Can be filtered by audience (show only to user or assistant)
- Priority can affect display order

### 2. ImageContent

**MCP Structure:**
```python
{
    "type": "image",
    "data": "base64_encoded_image_data",
    "mimeType": "image/png",
    "annotations": {
        "title": "Chart showing results"
    }
}
```

**Processing:**
1. Base64 data is decoded
2. Image is uploaded to Open WebUI storage
3. URL is returned and added to `tool_result_files`
4. Frontend displays image inline
5. LLM receives `[Image: image/png]` reference

**Example Use Cases:**
- Data visualization tools generating charts
- Image generation tools
- Screenshot/diagram tools
- QR code generators

### 3. AudioContent

**MCP Structure:**
```python
{
    "type": "audio",
    "data": "base64_encoded_audio_data",
    "mimeType": "audio/wav",
    "annotations": {
        "duration": 5.2
    }
}
```

**Processing:**
1. Base64 data is decoded
2. Audio is uploaded to storage
3. Audio player widget is shown in UI
4. LLM receives `[Audio: audio/wav]` reference

**Example Use Cases:**
- Text-to-speech tools
- Audio synthesis
- Voice message generation
- Music/sound generation

### 4. EmbeddedResource

**MCP Structure:**
```python
{
    "type": "resource",
    "resource": {
        "type": "text",  # or "blob"
        "uri": "file:///path/to/file.txt",
        "text": "Content of the file",
        "mimeType": "text/plain"
    }
}
```

**Processing:**
- Text resources are included in result
- Blob resources can be processed like images/audio
- URI provides context about source

**Example Use Cases:**
- File reading tools
- Database query results as resources
- API responses wrapped as resources

### 5. Structured Content

**MCP Structure:**
```python
{
    "content": [...],  # Normal content blocks
    "structuredContent": {
        "results": [
            {"name": "Item 1", "value": 42},
            {"name": "Item 2", "value": 87}
        ],
        "total": 129
    }
}
```

**Processing:**
- Validated against `outputSchema` if provided
- Available as typed data for programmatic use
- Also serialized as JSON for LLM
- Can be displayed in structured UI components

**Example Use Cases:**
- Database queries returning structured rows
- API responses with typed data
- Calculator/math tools with precise values
- Search results with metadata

## Progress Reporting

### Flow

```
┌──────────┐                  ┌──────────┐                  ┌──────────┐
│  Client  │                  │  Server  │                  │    UI    │
└────┬─────┘                  └────┬─────┘                  └────┬─────┘
     │                             │                             │
     │ call_tool({                 │                             │
     │   _meta: {progressToken}    │                             │
     │ })                          │                             │
     ├────────────────────────────>│                             │
     │                             │                             │
     │                             │ Processing...               │
     │                             │                             │
     │<─ notifications/progress ───┤                             │
     │   {progress: 0.33, total: 1}│                             │
     ├─────────────────────────────────────────────────────────>│
     │                                              [████░░░░░░] 33%
     │                             │                             │
     │<─ notifications/progress ───┤                             │
     │   {progress: 0.66, total: 1}│                             │
     ├─────────────────────────────────────────────────────────>│
     │                                              [███████░░░] 66%
     │                             │                             │
     │<─ CallToolResult ────────────┤                             │
     │   {content: [...]}          │                             │
     ├─────────────────────────────────────────────────────────>│
     │                                              [██████████] Done!
```

### Implementation

**Client Side:**
```python
# Generate unique progress token
progress_token = str(uuid4())

# Create callback for updates
async def on_progress(progress_data):
    await event_emitter({
        "type": "tool_progress",
        "data": {
            "tool": "generate_report",
            "progress": progress_data["progress"],
            "total": progress_data["total"],
            "percentage": progress_data["percentage"],
            "message": progress_data["message"]
        }
    })

# Call tool with progress tracking
result = await client.call_tool(
    "generate_report",
    {"query": "Q4 results"},
    progress_callback=on_progress
)
```

**Server Side (MCP Tool):**
```python
@mcp.tool()
async def generate_report(query: str, ctx: Context) -> str:
    """Generate a comprehensive report"""

    steps = 5
    for i in range(steps):
        # Do work...
        await asyncio.sleep(1)

        # Report progress
        await ctx.report_progress(
            progress=(i + 1) / steps,
            total=1.0,
            message=f"Step {i+1}/{steps}: Processing..."
        )

    return "Report complete!"
```

## Real-World Examples

### Example 1: Data Visualization Tool

**MCP Server Returns:**
```python
CallToolResult(
    content=[
        TextContent(
            type="text",
            text="Analysis complete. Generated visualization.",
            annotations={"audience": ["user"]}
        ),
        ImageContent(
            type="image",
            data="base64_chart_data...",
            mimeType="image/png",
            annotations={"title": "Q4 Sales by Region"}
        ),
        TextContent(
            type="text",
            text="The chart shows strong performance in APAC region with 45% growth.",
            annotations={"audience": ["assistant"]}
        )
    ],
    structuredContent={
        "regions": [
            {"name": "APAC", "sales": 145000, "growth": 0.45},
            {"name": "EMEA", "sales": 123000, "growth": 0.12},
            {"name": "AMER", "sales": 189000, "growth": 0.23}
        ]
    }
)
```

**Open WebUI Processing:**
1. First text block shown to user: "Analysis complete..."
2. Chart image uploaded and displayed inline
3. Second text block given to LLM only: "The chart shows..."
4. Structured data available for queries

**User Sees:**
```
Analysis complete. Generated visualization.

[Chart Image Displayed Here]
```

**LLM Sees:**
```
Analysis complete. Generated visualization.
[Image: image/png]
The chart shows strong performance in APAC region with 45% growth.

[Structured Data]
{
  "regions": [
    {"name": "APAC", "sales": 145000, "growth": 0.45},
    ...
  ]
}
```

### Example 2: Text-to-Speech Tool

**MCP Server Returns:**
```python
CallToolResult(
    content=[
        AudioContent(
            type="audio",
            data="base64_audio_data...",
            mimeType="audio/mp3",
            annotations={
                "duration": 3.5,
                "voice": "en-US-Neural"
            }
        ),
        TextContent(
            type="text",
            text='Generated speech: "Hello, how can I help you today?"'
        )
    ]
)
```

**User Sees:**
```
[Audio Player: 0:00 / 0:03 ▶️]

Generated speech: "Hello, how can I help you today?"
```

### Example 3: Long-Running Analysis with Progress

**User Asks:** "Analyze the last 1000 transactions for anomalies"

**Tool Execution:**
```
┌──────────────────────────────────────────┐
│ Analyzing transactions...                │
│ ████████████████░░░░░░░░░░░░░░░░  40%  │
│ Step 2/5: Checking patterns...           │
└──────────────────────────────────────────┘
```

Progress updates sent:
1. `progress=0.2, message="Step 1/5: Loading data..."`
2. `progress=0.4, message="Step 2/5: Checking patterns..."`
3. `progress=0.6, message="Step 3/5: Detecting anomalies..."`
4. `progress=0.8, message="Step 4/5: Scoring results..."`
5. `progress=1.0, message="Step 5/5: Generating report..."`

**Final Result:**
```python
CallToolResult(
    content=[
        TextContent(
            type="text",
            text="Found 3 anomalous transactions:"
        ),
        ImageContent(
            type="image",
            data="base64_chart...",
            mimeType="image/png"
        )
    ],
    structuredContent={
        "anomalies": [
            {
                "transaction_id": "TX-1234",
                "amount": 9999.99,
                "anomaly_score": 0.95,
                "reason": "Unusual amount for this merchant"
            },
            ...
        ],
        "total_checked": 1000,
        "total_anomalies": 3
    }
)
```

## Benefits

### 1. Better User Experience

**Before:**
```
Tool output: {"image": "base64...", "result": "Analysis complete"}
```
User has to decode/interpret raw JSON.

**After:**
```
Analysis complete.

[Beautiful Chart Displayed]

Found 3 anomalies in the data.
```
Rich, interactive display with images, audio, progress.

### 2. Better LLM Context

**Before:**
```
Tool output: [Long base64 string taking up 5000 tokens...]
```

**After:**
```
[Image: chart.png showing sales data]

Structured data shows APAC region leads with 45% growth.
```
Concise references + structured data = better token efficiency.

### 3. Type Safety

**Before:**
```python
result = call_tool(...)  # Returns: str (maybe JSON?)
# Hope it's valid JSON
data = json.loads(result)
# Hope it has the fields we need
value = data["results"][0]["value"]  # Might crash!
```

**After:**
```python
result = call_tool(...)  # Returns: MCPToolResult
# Structured content validated against schema
value = result.structured_content["results"][0]["value"]  # Type-safe!
```

### 4. Progress Visibility

**Before:**
```
User: "Analyze this large dataset"
[30 seconds of silence...]
User: "Is it working???"
```

**After:**
```
User: "Analyze this large dataset"
[Progress bar: 45% - Processing entries 4500/10000...]
User: 😊 "Ah, it's working"
```

### 5. Audience Targeting

**Before:**
All tool output goes to both user and LLM, even if some parts are only relevant to one.

**After:**
```python
# Technical details for LLM only
TextContent(
    text="Processed 10,000 rows, filtered 234 outliers using IQR method",
    annotations={"audience": ["assistant"]}
)

# User-friendly summary
TextContent(
    text="Found 234 unusual entries in your data.",
    annotations={"audience": ["user"]}
)
```

## Integration Steps

### Step 1: Update MCP Client

Replace `/backend/open_webui/utils/mcp/client.py` to use enhanced client:

```python
from open_webui.utils.mcp.client_enhanced import MCPClient
```

The enhanced client is backward compatible but adds:
- Progress tracking
- Content parsing
- Output schema support

### Step 2: Update Middleware

In `/backend/open_webui/utils/middleware.py` around line 1285:

```python
from open_webui.utils.mcp.middleware_integration import (
    process_mcp_tool_result,
    create_mcp_progress_callback
)

def make_tool_function(client, function_name):
    async def tool_function(**kwargs):
        # Create progress callback
        progress_callback = None
        if event_emitter:
            progress_callback = await create_mcp_progress_callback(
                event_emitter, function_name
            )

        # Call with enhanced features
        mcp_result = await client.call_tool(
            function_name,
            function_args=kwargs,
            progress_callback=progress_callback
        )

        # Process result
        return await process_mcp_tool_result(
            request,
            function_name,
            mcp_result,
            event_emitter,
            metadata,
            user
        )

    return tool_function
```

### Step 3: Frontend Updates

Add event handlers for new event types:

1. **`tool_progress`** - Display progress bars
2. **Enhanced `files`** - Handle audio files
3. **`structured_data`** - Render structured content

### Step 4: Testing

Test with MCP servers that support rich content:

```bash
# Example: Test with a server that returns images
curl http://localhost:8080/api/chat/completions \
  -d '{
    "messages": [{
      "role": "user",
      "content": "Generate a chart of sales data"
    }],
    "tools": ["mcp_visualization_server_create_chart"]
  }'
```

## Performance Considerations

### Token Efficiency

**Before:**
- Base64 image in tool result: ~5,000 tokens
- Total context: ~10,000 tokens

**After:**
- Image reference: ~10 tokens
- Structured data: ~500 tokens
- Total context: ~3,000 tokens

**Savings: 70% token reduction!**

### Bandwidth

- Images/audio stored once, referenced by URL
- Structured content is compact JSON
- Progress updates are lightweight

### Compatibility

- Backward compatible with existing tools
- Falls back gracefully if server doesn't support rich content
- Opt-in for advanced features

## Future Enhancements

1. **Video Content** - Add VideoContent support when MCP spec includes it
2. **Interactive Components** - Embed interactive widgets from tools
3. **Streaming Structured Content** - Stream structured data as it's generated
4. **Output Schema Validation** - Validate structured content against schemas
5. **Content Caching** - Cache large media content
6. **Annotation Actions** - Use annotations for automatic actions (e.g., priority sorting)

## Conclusion

This implementation transforms Open WebUI's MCP integration from basic text-only support to a rich, multi-media experience that:

- **Improves UX** with images, audio, and progress indicators
- **Reduces tokens** through efficient content references
- **Adds type safety** with structured content
- **Enables new use cases** like visualization, speech, and interactive tools
- **Maintains compatibility** with existing implementations

The modular design makes it easy to adopt incrementally, starting with basic content parsing and adding features like progress reporting as needed.
