# MCP Content Types - Concrete Examples

This document shows real before/after comparisons demonstrating the value of full MCP content type support.

## Example 1: Weather Forecast Tool with Chart

### Current Implementation (Text Only)

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"forecast\": [{\"day\": \"Monday\", \"temp\": 72, \"condition\": \"Sunny\"}, {\"day\": \"Tuesday\", \"temp\": 68, \"condition\": \"Cloudy\"}], \"chart_base64\": \"iVBORw0KGgoAAAANSUhEUgAAAAUA...\" }"
    }
  ]
}
```

**What User Sees:**
```
{"forecast": [{"day": "Monday", "temp": 72, "condition": "Sunny"}, {"day": "Tuesday", "temp": 68, "condition": "Cloudy"}], "chart_base64": "iVBORw0KGgoAAAANSUhEUgAAAAUA..."}
```

**Problems:**
- Raw JSON is ugly and hard to read
- Base64 string is meaningless to users
- LLM wastes tokens processing base64
- No image is displayed

### Enhanced Implementation (Full Content Types)

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Here's your 7-day forecast:",
      "annotations": {"audience": ["user"]}
    },
    {
      "type": "image",
      "data": "iVBORw0KGgoAAAANSUhEUgAAAAUA...",
      "mimeType": "image/png",
      "annotations": {"title": "7-Day Temperature Forecast"}
    },
    {
      "type": "text",
      "text": "Temperatures will range from 65-75°F. Sunny Monday, cloudy Tuesday-Wednesday, rain Thursday.",
      "annotations": {"audience": ["assistant"]}
    }
  ],
  "structuredContent": {
    "forecast": [
      {"day": "Monday", "temp": 72, "condition": "Sunny", "precipitation": 0},
      {"day": "Tuesday", "temp": 68, "condition": "Cloudy", "precipitation": 10},
      {"day": "Wednesday", "temp": 70, "condition": "Cloudy", "precipitation": 20},
      {"day": "Thursday", "temp": 67, "condition": "Rain", "precipitation": 80}
    ],
    "summary": {
      "avg_temp": 69,
      "precipitation_days": 2
    }
  }
}
```

**What User Sees:**
```
Here's your 7-day forecast:

[Beautiful weather chart with bars showing temperatures and icons]

```

**What LLM Sees:**
```
Here's your 7-day forecast:
[Image: 7-Day Temperature Forecast]
Temperatures will range from 65-75°F. Sunny Monday, cloudy Tuesday-Wednesday, rain Thursday.

[Structured Data]
{
  "forecast": [...],
  "summary": {"avg_temp": 69, "precipitation_days": 2}
}
```

**Benefits:**
- ✅ User sees beautiful chart
- ✅ LLM gets concise summary + structured data
- ✅ Can query structured data: "What's the average temperature?"
- ✅ Tokens reduced from ~3000 to ~300

---

## Example 2: Text-to-Speech Tool

### Current Implementation

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Audio generated. Base64: data:audio/mp3;base64,//uQxAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAA..."
    }
  ]
}
```

**What User Sees:**
```
Audio generated. Base64: data:audio/mp3;base64,//uQxAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAA...
```

**Problems:**
- User can't play the audio
- Has to manually decode base64
- Takes up 5000+ tokens in context

### Enhanced Implementation

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "audio",
      "data": "//uQxAAAAAAAAAAAAAAAAAAAAAAASW5mbwAAAA8AAAA...",
      "mimeType": "audio/mp3",
      "annotations": {
        "duration": 4.2,
        "voice": "en-US-Neural-Female",
        "text": "Hello! How can I help you today?"
      }
    },
    {
      "type": "text",
      "text": "Generated speech audio (4.2 seconds)."
    }
  ]
}
```

**What User Sees:**
```
🔊 Hello! How can I help you today?
   0:00 ━━━━━━━━━━━━━━━━━━━━━━ 0:04 ▶️ 🔇

Generated speech audio (4.2 seconds).
```

**What LLM Sees:**
```
[Audio: audio/mp3, 4.2s - "Hello! How can I help you today?"]
Generated speech audio (4.2 seconds).
```

**Benefits:**
- ✅ User can play audio directly
- ✅ Shows waveform and controls
- ✅ LLM gets concise reference
- ✅ Tokens reduced from ~5000 to ~30

---

## Example 3: Database Query Tool with Progress

### Current Implementation

**User:** "Find all customers who haven't purchased in 6 months"

**Tool Execution:**
```
[30 seconds of waiting...]
[Finally returns...]
```

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "[{\"customer_id\": 1001, \"name\": \"John Doe\", \"last_purchase\": \"2024-05-01\", \"total_spent\": 1250}, {\"customer_id\": 1005, \"name\": \"Jane Smith\", \"last_purchase\": \"2024-04-15\", \"total_spent\": 890}, ... 500 more customers ...]"
    }
  ]
}
```

**Problems:**
- User has no idea if it's working
- Might timeout
- Returns massive JSON blob
- Wastes tokens on full customer list

### Enhanced Implementation

**User:** "Find all customers who haven't purchased in 6 months"

**Tool Execution with Progress:**
```
┌────────────────────────────────────────┐
│ Finding inactive customers...          │
│ ████████████████░░░░░░░░  60%         │
│ Scanned 6,000 / 10,000 customers       │
└────────────────────────────────────────┘
```

Progress updates emitted:
```javascript
{type: "tool_progress", data: {
  tool: "query_customers",
  progress: 0.2,
  total: 1.0,
  percentage: 20,
  message: "Scanning customer database..."
}}

{type: "tool_progress", data: {
  tool: "query_customers",
  progress: 0.4,
  total: 1.0,
  percentage: 40,
  message: "Filtering by purchase date..."
}}

{type: "tool_progress", data: {
  tool: "query_customers",
  progress: 0.6,
  total: 1.0,
  percentage: 60,
  message: "Scanned 6,000 / 10,000 customers"
}}
```

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 523 customers who haven't purchased in 6+ months.",
      "annotations": {"audience": ["user"]}
    },
    {
      "type": "text",
      "text": "Top 10 by lifetime value are in structured data. Total represents $147,890 in at-risk revenue.",
      "annotations": {"audience": ["assistant"]}
    }
  ],
  "structuredContent": {
    "query": {
      "total_customers_scanned": 10000,
      "inactive_count": 523,
      "total_at_risk_revenue": 147890
    },
    "top_customers": [
      {"customer_id": 1001, "name": "John Doe", "last_purchase": "2024-05-01", "total_spent": 1250},
      {"customer_id": 1005, "name": "Jane Smith", "last_purchase": "2024-04-15", "total_spent": 890},
      ...
    ]
  }
}
```

**What User Sees:**
```
[Progress bar animating]

Found 523 customers who haven't purchased in 6+ months.
```

**What LLM Sees:**
```
Found 523 customers who haven't purchased in 6+ months.
Top 10 by lifetime value are in structured data. Total represents $147,890 in at-risk revenue.

[Structured Data]
{
  "query": {
    "total_customers_scanned": 10000,
    "inactive_count": 523,
    "total_at_risk_revenue": 147890
  },
  "top_customers": [...]
}
```

**Benefits:**
- ✅ User sees progress (knows it's working)
- ✅ Summary instead of full list
- ✅ Structured data for follow-up queries
- ✅ Tokens reduced from ~50,000 to ~500
- ✅ Can ask "Who's the top customer?" without re-running

---

## Example 4: Code Execution Tool with Multiple Outputs

### Current Implementation

**User:** "Run this Python code and show me the results"

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Output:\nHello World\n\nPlot saved as: data:image/png;base64,iVBORw0KG...\n\nStats:\n{'mean': 5.5, 'median': 5.0, 'std': 2.87}"
    }
  ]
}
```

**Problems:**
- Everything mashed together
- Image not displayed
- No structure to stats

### Enhanced Implementation

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Code executed successfully. Output:",
      "annotations": {"audience": ["user"]}
    },
    {
      "type": "text",
      "text": "Hello World",
      "annotations": {"audience": ["user", "assistant"]}
    },
    {
      "type": "image",
      "data": "iVBORw0KG...",
      "mimeType": "image/png",
      "annotations": {"title": "Data Visualization"}
    },
    {
      "type": "text",
      "text": "Statistical analysis shows mean=5.5, median=5.0, std=2.87",
      "annotations": {"audience": ["assistant"]}
    }
  ],
  "structuredContent": {
    "stdout": "Hello World",
    "stderr": "",
    "exit_code": 0,
    "execution_time": 0.245,
    "statistics": {
      "mean": 5.5,
      "median": 5.0,
      "std": 2.87,
      "count": 10
    }
  }
}
```

**What User Sees:**
```
Code executed successfully. Output:

Hello World

[Beautiful plot displayed]
```

**What LLM Sees:**
```
Code executed successfully. Output:
Hello World
[Image: Data Visualization]
Statistical analysis shows mean=5.5, median=5.0, std=2.87

[Structured Data]
{
  "stdout": "Hello World",
  "statistics": {...}
}
```

**Benefits:**
- ✅ Clean separation of concerns
- ✅ Image displayed inline
- ✅ Structured stats for queries
- ✅ Can ask "What was the standard deviation?" without re-running

---

## Example 5: File Analysis Tool

### Current Implementation

**User:** "Analyze this CSV file"

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Analysis: File has 1000 rows, 5 columns. Column types: id(int), name(str), amount(float), date(str), category(str). Sample data: [['1', 'Item A', '99.99', '2024-01-15', 'Electronics'], ['2', 'Item B', '45.50', '2024-01-16', 'Books']]"
    }
  ]
}
```

**Problems:**
- Wall of text
- No visualization
- Hard to understand patterns

### Enhanced Implementation

**Tool Returns:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "Analyzed CSV file with 1,000 rows and 5 columns."
    },
    {
      "type": "image",
      "data": "...",
      "mimeType": "image/png",
      "annotations": {"title": "Distribution of Categories"}
    },
    {
      "type": "image",
      "data": "...",
      "mimeType": "image/png",
      "annotations": {"title": "Amount Over Time"}
    },
    {
      "type": "text",
      "text": "Key insights: Electronics category dominates (45%), average purchase $67.50, highest activity in January."
    }
  ],
  "structuredContent": {
    "summary": {
      "total_rows": 1000,
      "columns": ["id", "name", "amount", "date", "category"],
      "date_range": {"start": "2024-01-01", "end": "2024-12-31"}
    },
    "statistics": {
      "total_amount": 67500.00,
      "average_amount": 67.50,
      "category_distribution": {
        "Electronics": 450,
        "Books": 300,
        "Clothing": 250
      }
    }
  }
}
```

**What User Sees:**
```
Analyzed CSV file with 1,000 rows and 5 columns.

[Pie chart showing category distribution]

[Line chart showing amount over time]

Key insights: Electronics category dominates (45%), average purchase $67.50, highest activity in January.
```

**Benefits:**
- ✅ Visual understanding
- ✅ Multiple charts
- ✅ Structured data for queries
- ✅ "What percentage was Electronics?" → instant answer

---

## Token Savings Summary

| Scenario | Before (tokens) | After (tokens) | Savings |
|----------|----------------|----------------|---------|
| Weather with chart | ~3,000 | ~300 | 90% |
| Text-to-speech | ~5,000 | ~30 | 99% |
| Database query | ~50,000 | ~500 | 99% |
| Code execution | ~4,000 | ~400 | 90% |
| File analysis | ~8,000 | ~600 | 92% |

**Average savings: 94% fewer tokens while providing BETTER information!**

---

## User Experience Comparison

### Before: Text-Only
```
User: "Show me sales data"
Assistant: "Here's the data as JSON..."
User: *sees 5000 lines of JSON*
User: 😵 "Uh, can you summarize?"
Assistant: "Sure..." *uses more tokens*
```

### After: Rich Content
```
User: "Show me sales data"
Assistant: "Here's your sales dashboard:"
User: *sees beautiful charts*
User: 😍 "Perfect! What region performed best?"
Assistant: *checks structured data*
"APAC led with 45% growth!"
User: ✨
```

---

## Technical Comparison

### Current Code (client.py lines 68-74)

```python
result_dict = result.model_dump(mode="json")
result_content = result_dict.get("content", {})

if result.isError:
    raise Exception(result_content)
else:
    return result_content  # Just dumps everything as dict
```

**Problems:**
- Loses type information
- No media processing
- No progress support
- No structured content access

### Enhanced Code

```python
# Parse with full type support
parsed_result = MCPContentParser.parse_tool_result(result_dict)

# Process images/audio
result_text, result_files, result_embeds = await process_mcp_tool_result(
    request, tool_name, parsed_result, event_emitter, metadata, user
)

# Files automatically uploaded and URLs returned
# Images displayed inline
# Audio embedded with player
# Progress shown in real-time
# Structured content available for queries
```

**Benefits:**
- ✅ Full type safety
- ✅ Automatic media handling
- ✅ Progress tracking
- ✅ Structured data access
- ✅ Audience filtering
- ✅ Token efficiency

---

## Real-World Impact

### Scenario: Data Science Workflow

**User:** "Analyze this dataset and show me insights"

**With Text-Only:**
1. Tool runs for 30 seconds (no feedback)
2. Returns 50KB of JSON
3. User can't see charts
4. LLM tries to describe data (uses 5000 tokens)
5. User asks for specific stat
6. Re-runs entire analysis
7. Wastes time and tokens

**With Rich Content:**
1. Tool shows progress: "Loading... Analyzing... Generating charts..."
2. Returns 3 charts + summary + structured data
3. User sees beautiful visualizations
4. LLM has structured data ready
5. User asks for specific stat
6. Instant answer from structured data
7. No re-run needed!

**Time saved:** 2 minutes per query
**Tokens saved:** 95%
**User satisfaction:** 📈📈📈

---

## Conclusion

Full MCP content type support transforms Open WebUI from a basic text interface into a rich, multi-media experience that:

- **Saves 90%+ tokens** through efficient content representation
- **Improves UX** with images, audio, progress, and structure
- **Enables new use cases** that weren't possible before
- **Maintains compatibility** with existing tools

The implementation is modular and can be adopted incrementally, with immediate benefits at each stage.
