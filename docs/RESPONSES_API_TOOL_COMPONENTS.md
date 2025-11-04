# Responses API - Tool Components & UI Reference

Complete reference for implementing native tool support in Open WebUI's frontend.

---

## Frontend Tool Components

### 1. Code Interpreter Result Component

**File:** `/src/lib/components/tools/CodeExecutionResult.svelte`

```svelte
<script lang="ts">
    export let toolCall: {
        id: string;
        code: string;
        execution_output: string;
        status: string;
        error?: any;
    };

    let showCode = false;
    let copyButtonText = 'Copy';

    const copyCode = async () => {
        await navigator.clipboard.writeText(toolCall.code);
        copyButtonText = 'Copied!';
        setTimeout(() => copyButtonText = 'Copy', 2000);
    };
</script>

<div class="code-execution-result">
    <div class="header">
        <div class="icon">
            <svg><!-- Code icon --></svg>
        </div>
        <div class="title">
            <span class="font-semibold">Code Interpreter</span>
            <span class="status" class:success={toolCall.status === 'completed'} class:error={toolCall.status === 'failed'}>
                {toolCall.status}
            </span>
        </div>
        <button on:click={() => showCode = !showCode} class="toggle-btn">
            {showCode ? 'Hide' : 'Show'} Code
        </button>
    </div>

    {#if showCode}
        <div class="code-block">
            <div class="code-header">
                <span class="language">Python</span>
                <button on:click={copyCode} class="copy-btn">
                    {copyButtonText}
                </button>
            </div>
            <pre><code class="language-python">{toolCall.code}</code></pre>
        </div>
    {/if}

    {#if toolCall.execution_output}
        <div class="output-block">
            <div class="output-label">Output:</div>
            <pre class="output-content">{toolCall.execution_output}</pre>
        </div>
    {/if}

    {#if toolCall.error}
        <div class="error-block">
            <div class="error-icon">⚠️</div>
            <div class="error-message">{toolCall.error.message || JSON.stringify(toolCall.error)}</div>
        </div>
    {/if}
</div>

<style>
    .code-execution-result {
        @apply border border-blue-200 dark:border-blue-800 rounded-lg overflow-hidden;
    }

    .header {
        @apply flex items-center gap-3 p-3 bg-blue-50 dark:bg-blue-900/20;
    }

    .icon {
        @apply w-8 h-8 flex items-center justify-center bg-blue-500 text-white rounded;
    }

    .title {
        @apply flex-1 flex items-center gap-2;
    }

    .status {
        @apply text-xs px-2 py-1 rounded-full;
    }

    .status.success {
        @apply bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300;
    }

    .status.error {
        @apply bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300;
    }

    .code-block {
        @apply border-t border-blue-200 dark:border-blue-800;
    }

    .code-header {
        @apply flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-gray-800;
    }

    pre code {
        @apply block p-4 overflow-x-auto;
    }

    .output-block {
        @apply border-t border-blue-200 dark:border-blue-800 p-4 bg-gray-50 dark:bg-gray-900/50;
    }

    .output-content {
        @apply mt-2 p-3 bg-white dark:bg-black rounded border border-gray-200 dark:border-gray-700 font-mono text-sm overflow-x-auto;
    }

    .error-block {
        @apply flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border-t border-red-200 dark:border-red-800;
    }
</style>
```

### 2. Image Generation Result Component

**File:** `/src/lib/components/tools/ImageGenerationResult.svelte`

```svelte
<script lang="ts">
    import { createEventDispatcher } from 'svelte';

    export let toolCall: {
        id: string;
        prompt: string;
        images: string[];
        status: string;
    };

    const dispatch = createEventDispatcher();

    let selectedImage = toolCall.images?.[0];
    let showPrompt = false;

    const downloadImage = async (url: string, index: number) => {
        const response = await fetch(url);
        const blob = await response.blob();
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `generated-image-${index + 1}.png`;
        link.click();
    };

    const editImage = (prompt: string) => {
        dispatch('edit-image', { prompt });
    };
</script>

<div class="image-generation-result">
    <div class="header">
        <div class="icon">
            <svg><!-- Image icon --></svg>
        </div>
        <div class="title">
            <span class="font-semibold">Image Generation</span>
            <span class="badge">{toolCall.images?.length || 0} image{toolCall.images?.length !== 1 ? 's' : ''}</span>
        </div>
        <button on:click={() => showPrompt = !showPrompt} class="toggle-btn">
            {showPrompt ? 'Hide' : 'Show'} Prompt
        </button>
    </div>

    {#if showPrompt && toolCall.prompt}
        <div class="prompt-block">
            <div class="prompt-label">Prompt:</div>
            <div class="prompt-text">{toolCall.prompt}</div>
        </div>
    {/if}

    <div class="images-container">
        {#if toolCall.images && toolCall.images.length > 0}
            <!-- Main image display -->
            <div class="main-image">
                <img src={selectedImage} alt="Generated image" />
                <div class="image-actions">
                    <button on:click={() => downloadImage(selectedImage, 0)} class="action-btn">
                        📥 Download
                    </button>
                    <button on:click={() => editImage(toolCall.prompt)} class="action-btn">
                        ✏️ Edit
                    </button>
                </div>
            </div>

            <!-- Thumbnail gallery (if multiple images) -->
            {#if toolCall.images.length > 1}
                <div class="thumbnails">
                    {#each toolCall.images as image, index}
                        <button
                            class="thumbnail"
                            class:selected={selectedImage === image}
                            on:click={() => selectedImage = image}
                        >
                            <img src={image} alt={`Generated image ${index + 1}`} />
                        </button>
                    {/each}
                </div>
            {/if}
        {:else if toolCall.status === 'running'}
            <div class="generating-placeholder">
                <div class="spinner"></div>
                <span>Generating image...</span>
            </div>
        {/if}
    </div>
</div>

<style>
    .image-generation-result {
        @apply border border-purple-200 dark:border-purple-800 rounded-lg overflow-hidden;
    }

    .header {
        @apply flex items-center gap-3 p-3 bg-purple-50 dark:bg-purple-900/20;
    }

    .badge {
        @apply text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/50 text-purple-800 dark:text-purple-300 rounded-full;
    }

    .prompt-block {
        @apply p-4 bg-gray-50 dark:bg-gray-900/50 border-t border-purple-200 dark:border-purple-800;
    }

    .prompt-text {
        @apply mt-2 p-3 bg-white dark:bg-black rounded border border-gray-200 dark:border-gray-700 text-sm;
    }

    .images-container {
        @apply p-4;
    }

    .main-image {
        @apply relative rounded-lg overflow-hidden bg-gray-100 dark:bg-gray-900;
    }

    .main-image img {
        @apply w-full h-auto;
    }

    .image-actions {
        @apply absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/70 to-transparent flex gap-2;
    }

    .action-btn {
        @apply px-4 py-2 bg-white/90 hover:bg-white rounded-lg font-medium transition-colors;
    }

    .thumbnails {
        @apply flex gap-2 mt-4 overflow-x-auto;
    }

    .thumbnail {
        @apply w-20 h-20 rounded-lg overflow-hidden border-2 transition-all;
        @apply border-transparent hover:border-purple-500;
    }

    .thumbnail.selected {
        @apply border-purple-500 ring-2 ring-purple-500/50;
    }

    .generating-placeholder {
        @apply flex flex-col items-center justify-center gap-4 p-12 bg-gray-50 dark:bg-gray-900/50 rounded-lg;
    }

    .spinner {
        @apply w-8 h-8 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin;
    }
</style>
```

### 3. File Search Result Component

**File:** `/src/lib/components/tools/FileSearchResult.svelte`

```svelte
<script lang="ts">
    export let toolCall: {
        id: string;
        file_ids: string[];
        results: Array<{
            file_id: string;
            file_name: string;
            score: number;
            snippet: string;
            page?: number;
        }>;
        status: string;
    };

    let showAllResults = false;
    $: displayedResults = showAllResults ? toolCall.results : toolCall.results?.slice(0, 3);
</script>

<div class="file-search-result">
    <div class="header">
        <div class="icon">
            <svg><!-- Search icon --></svg>
        </div>
        <div class="title">
            <span class="font-semibold">File Search</span>
            <span class="badge">{toolCall.results?.length || 0} result{toolCall.results?.length !== 1 ? 's' : ''}</span>
        </div>
    </div>

    {#if toolCall.results && toolCall.results.length > 0}
        <div class="results-list">
            {#each displayedResults as result}
                <div class="result-item">
                    <div class="result-header">
                        <div class="file-name">📄 {result.file_name}</div>
                        <div class="score">
                            <div class="score-bar" style="width: {result.score * 100}%"></div>
                        </div>
                    </div>
                    <div class="snippet">{result.snippet}</div>
                    {#if result.page}
                        <div class="page-number">Page {result.page}</div>
                    {/if}
                </div>
            {/each}
        </div>

        {#if toolCall.results.length > 3}
            <div class="show-more">
                <button on:click={() => showAllResults = !showAllResults} class="show-more-btn">
                    {showAllResults ? 'Show Less' : `Show ${toolCall.results.length - 3} More`}
                </button>
            </div>
        {/if}
    {:else if toolCall.status === 'running'}
        <div class="searching-placeholder">
            <div class="spinner"></div>
            <span>Searching files...</span>
        </div>
    {:else}
        <div class="no-results">
            No results found
        </div>
    {/if}
</div>

<style>
    .file-search-result {
        @apply border border-green-200 dark:border-green-800 rounded-lg overflow-hidden;
    }

    .header {
        @apply flex items-center gap-3 p-3 bg-green-50 dark:bg-green-900/20;
    }

    .results-list {
        @apply divide-y divide-gray-200 dark:divide-gray-700;
    }

    .result-item {
        @apply p-4 hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors;
    }

    .result-header {
        @apply flex items-center justify-between gap-4 mb-2;
    }

    .file-name {
        @apply font-medium text-sm;
    }

    .score {
        @apply w-24 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden;
    }

    .score-bar {
        @apply h-full bg-green-500 transition-all;
    }

    .snippet {
        @apply text-sm text-gray-700 dark:text-gray-300 line-clamp-3;
    }

    .page-number {
        @apply mt-2 text-xs text-gray-500;
    }

    .show-more {
        @apply p-3 border-t border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/10;
    }

    .show-more-btn {
        @apply w-full py-2 text-sm font-medium text-green-700 dark:text-green-400 hover:underline;
    }
</style>
```

### 4. Web Search Result Component

**File:** `/src/lib/components/tools/WebSearchResult.svelte`

```svelte
<script lang="ts">
    export let toolCall: {
        id: string;
        output: {
            results: Array<{
                title: string;
                url: string;
                snippet: string;
                favicon?: string;
            }>;
        };
        status: string;
    };

    let showAllResults = false;
    $: results = toolCall.output?.results || [];
    $: displayedResults = showAllResults ? results : results.slice(0, 5);
</script>

<div class="web-search-result">
    <div class="header">
        <div class="icon">🔍</div>
        <div class="title">
            <span class="font-semibold">Web Search</span>
            <span class="badge">{results.length} result{results.length !== 1 ? 's' : ''}</span>
        </div>
    </div>

    {#if results.length > 0}
        <div class="results-list">
            {#each displayedResults as result}
                <a href={result.url} target="_blank" rel="noopener noreferrer" class="result-item">
                    <div class="result-header">
                        {#if result.favicon}
                            <img src={result.favicon} alt="" class="favicon" />
                        {:else}
                            <div class="favicon-placeholder">🌐</div>
                        {/if}
                        <div class="result-title">{result.title}</div>
                        <svg class="external-link-icon" width="16" height="16" viewBox="0 0 16 16">
                            <path d="M13 3L3 13M13 3h-7M13 3v7" stroke="currentColor" stroke-width="2" fill="none"/>
                        </svg>
                    </div>
                    <div class="result-url">{new URL(result.url).hostname}</div>
                    <div class="result-snippet">{result.snippet}</div>
                </a>
            {/each}
        </div>

        {#if results.length > 5}
            <div class="show-more">
                <button on:click={() => showAllResults = !showAllResults} class="show-more-btn">
                    {showAllResults ? 'Show Less' : `Show ${results.length - 5} More`}
                </button>
            </div>
        {/if}
    {:else if toolCall.status === 'running'}
        <div class="searching-placeholder">
            <div class="spinner"></div>
            <span>Searching the web...</span>
        </div>
    {/if}
</div>

<style>
    .web-search-result {
        @apply border border-orange-200 dark:border-orange-800 rounded-lg overflow-hidden;
    }

    .header {
        @apply flex items-center gap-3 p-3 bg-orange-50 dark:bg-orange-900/20;
    }

    .results-list {
        @apply divide-y divide-gray-200 dark:divide-gray-700;
    }

    .result-item {
        @apply block p-4 hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors;
        @apply no-underline;
    }

    .result-header {
        @apply flex items-center gap-2 mb-1;
    }

    .favicon {
        @apply w-4 h-4 rounded;
    }

    .favicon-placeholder {
        @apply w-4 h-4 text-xs flex items-center justify-center;
    }

    .result-title {
        @apply flex-1 font-medium text-blue-600 dark:text-blue-400 hover:underline;
    }

    .external-link-icon {
        @apply opacity-50;
    }

    .result-url {
        @apply text-sm text-green-700 dark:text-green-400 mb-1;
    }

    .result-snippet {
        @apply text-sm text-gray-700 dark:text-gray-300 line-clamp-2;
    }
</style>
```

### 5. MCP Tool Result Component

**File:** `/src/lib/components/tools/MCPToolResult.svelte`

```svelte
<script lang="ts">
    export let toolCall: {
        id: string;
        name: string;
        server: {
            label: string;
            url: string;
        };
        input: any;
        output: any;
        status: string;
        error?: any;
    };

    let showDetails = false;

    const formatJSON = (data: any) => JSON.stringify(data, null, 2);
</script>

<div class="mcp-tool-result">
    <div class="header">
        <div class="icon">🔌</div>
        <div class="title">
            <div>
                <span class="font-semibold">{toolCall.name}</span>
                <span class="server-badge">{toolCall.server.label}</span>
            </div>
            <div class="status" class:success={toolCall.status === 'completed'} class:error={toolCall.status === 'failed'}>
                {toolCall.status}
            </div>
        </div>
        <button on:click={() => showDetails = !showDetails} class="toggle-btn">
            {showDetails ? '▼' : '▶'}
        </button>
    </div>

    {#if toolCall.output && typeof toolCall.output === 'object'}
        <div class="output-preview">
            {#if toolCall.output.message}
                <div class="message">{toolCall.output.message}</div>
            {:else if toolCall.output.data}
                <div class="data-preview">
                    {JSON.stringify(toolCall.output.data).substring(0, 200)}...
                </div>
            {:else}
                <div class="data-preview">
                    {JSON.stringify(toolCall.output).substring(0, 200)}...
                </div>
            {/if}
        </div>
    {/if}

    {#if showDetails}
        <div class="details">
            <div class="detail-section">
                <div class="detail-label">Server:</div>
                <div class="detail-value">{toolCall.server.url}</div>
            </div>

            {#if toolCall.input}
                <div class="detail-section">
                    <div class="detail-label">Input:</div>
                    <pre class="detail-json">{formatJSON(toolCall.input)}</pre>
                </div>
            {/if}

            {#if toolCall.output}
                <div class="detail-section">
                    <div class="detail-label">Output:</div>
                    <pre class="detail-json">{formatJSON(toolCall.output)}</pre>
                </div>
            {/if}

            {#if toolCall.error}
                <div class="detail-section error-section">
                    <div class="detail-label">Error:</div>
                    <pre class="detail-json">{formatJSON(toolCall.error)}</pre>
                </div>
            {/if}
        </div>
    {/if}
</div>

<style>
    .mcp-tool-result {
        @apply border border-indigo-200 dark:border-indigo-800 rounded-lg overflow-hidden;
    }

    .header {
        @apply flex items-center gap-3 p-3 bg-indigo-50 dark:bg-indigo-900/20;
    }

    .title {
        @apply flex-1;
    }

    .server-badge {
        @apply ml-2 text-xs px-2 py-1 bg-indigo-100 dark:bg-indigo-900/50 text-indigo-800 dark:text-indigo-300 rounded-full;
    }

    .output-preview {
        @apply p-4 bg-gray-50 dark:bg-gray-900/50 border-t border-indigo-200 dark:border-indigo-800;
    }

    .message {
        @apply text-sm;
    }

    .data-preview {
        @apply text-sm font-mono text-gray-600 dark:text-gray-400;
    }

    .details {
        @apply border-t border-indigo-200 dark:border-indigo-800 bg-white dark:bg-gray-900;
    }

    .detail-section {
        @apply p-4 border-b border-gray-200 dark:border-gray-700 last:border-b-0;
    }

    .detail-label {
        @apply text-sm font-medium text-gray-700 dark:text-gray-300 mb-2;
    }

    .detail-value {
        @apply text-sm text-gray-600 dark:text-gray-400 font-mono;
    }

    .detail-json {
        @apply p-3 bg-gray-100 dark:bg-black rounded border border-gray-200 dark:border-gray-700 font-mono text-xs overflow-x-auto;
    }

    .error-section {
        @apply bg-red-50 dark:bg-red-900/10;
    }
</style>
```

---

## Streaming Event Handler

**File:** `/src/lib/apis/responses/streaming.ts`

```typescript
/**
 * Handle Server-Sent Events (SSE) from Responses API streaming.
 *
 * Responses API uses full SSE protocol with typed events:
 * event: response.output_text.delta
 * data: {"delta": {"text": "Hello"}}
 */

export interface StreamEvent {
    event: string;
    data: any;
}

export class ResponsesStreamHandler {
    private reader: ReadableStreamDefaultReader<Uint8Array>;
    private decoder = new TextDecoder();
    private buffer = '';

    constructor(response: Response) {
        if (!response.body) {
            throw new Error('Response has no body');
        }
        this.reader = response.body.getReader();
    }

    async *[Symbol.asyncIterator](): AsyncIterableIterator<StreamEvent> {
        let currentEvent: string | null = null;

        while (true) {
            const { done, value } = await this.reader.read();

            if (done) {
                break;
            }

            this.buffer += this.decoder.decode(value, { stream: true });

            const lines = this.buffer.split('\n');
            this.buffer = lines.pop() || '';

            for (const line of lines) {
                const trimmed = line.trim();

                if (!trimmed) {
                    continue;
                }

                if (trimmed.startsWith('event:')) {
                    currentEvent = trimmed.substring(6).trim();
                } else if (trimmed.startsWith('data:')) {
                    const dataStr = trimmed.substring(5).trim();

                    try {
                        const data = JSON.parse(dataStr);

                        if (currentEvent) {
                            yield {
                                event: currentEvent,
                                data
                            };
                        }
                    } catch (e) {
                        console.error('Failed to parse SSE data:', dataStr, e);
                    }

                    currentEvent = null;
                }
            }
        }
    }

    cancel() {
        this.reader.cancel();
    }
}

/**
 * Process streaming events and update response state
 */
export async function processResponseStream(
    response: Response,
    onUpdate: (update: ResponseUpdate) => void
): Promise<void> {
    const stream = new ResponsesStreamHandler(response);

    let currentOutput = '';
    let currentReasoning = '';
    const toolCalls: any[] = [];

    try {
        for await (const event of stream) {
            switch (event.event) {
                case 'response.created':
                    onUpdate({
                        type: 'created',
                        responseId: event.data.id,
                        status: event.data.status
                    });
                    break;

                case 'response.output_text.delta':
                    currentOutput += event.data.delta?.text || '';
                    onUpdate({
                        type: 'output_delta',
                        text: event.data.delta?.text || '',
                        fullText: currentOutput
                    });
                    break;

                case 'response.reasoning_summary_text.delta':
                    currentReasoning += event.data.delta?.text || '';
                    onUpdate({
                        type: 'reasoning_delta',
                        text: event.data.delta?.text || '',
                        fullText: currentReasoning
                    });
                    break;

                case 'response.output_item.added':
                    // New output item (could be tool call)
                    if (event.data.item?.type === 'tool_use') {
                        toolCalls.push({
                            id: event.data.item.id,
                            type: event.data.item.tool_type,
                            status: 'running',
                            ...event.data.item
                        });
                        onUpdate({
                            type: 'tool_call_started',
                            toolCall: event.data.item
                        });
                    }
                    break;

                case 'response.output_item.done':
                    // Tool call completed
                    const doneItem = event.data.item;
                    if (doneItem?.type === 'tool_use') {
                        const toolIndex = toolCalls.findIndex(t => t.id === doneItem.id);
                        if (toolIndex !== -1) {
                            toolCalls[toolIndex] = {
                                ...toolCalls[toolIndex],
                                status: 'completed',
                                output: doneItem.output
                            };
                            onUpdate({
                                type: 'tool_call_completed',
                                toolCall: toolCalls[toolIndex]
                            });
                        }
                    }
                    break;

                case 'response.completed':
                    onUpdate({
                        type: 'completed',
                        response: {
                            id: event.data.id,
                            status: 'completed',
                            output_text: currentOutput,
                            reasoning_summary: currentReasoning,
                            tool_calls: toolCalls,
                            usage: event.data.usage,
                            ...event.data
                        }
                    });
                    break;

                case 'response.failed':
                    onUpdate({
                        type: 'failed',
                        error: event.data.error
                    });
                    break;

                default:
                    console.log('Unknown event type:', event.event, event.data);
            }
        }
    } catch (error) {
        console.error('Stream processing error:', error);
        onUpdate({
            type: 'error',
            error: error
        });
    }
}

export interface ResponseUpdate {
    type: 'created' | 'output_delta' | 'reasoning_delta' | 'tool_call_started' | 'tool_call_completed' | 'completed' | 'failed' | 'error';
    [key: string]: any;
}
```

---

## Response Store (State Management)

**File:** `/src/lib/stores/responses.ts`

```typescript
import { writable, derived, get } from 'svelte/store';
import type { Writable, Readable } from 'svelte/store';

export interface Response {
    id: string;
    chat_id: string;
    model: string;
    created_at: number;
    status: 'queued' | 'in_progress' | 'completed' | 'failed';
    output_text: string;
    reasoning_summary?: string;
    tool_calls: ToolCall[];
    artifacts: Artifact[];
    usage?: {
        prompt_tokens: number;
        completion_tokens: number;
        total_tokens: number;
    };
    costs: {
        base: number;
        tools: Record<string, number>;
        total: number;
    };
    metadata: Record<string, any>;
}

export interface ToolCall {
    id: string;
    type: 'mcp' | 'code_interpreter' | 'file_search' | 'image_generation' | 'web_search_preview';
    name?: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    input: any;
    output: any;
    error?: any;
    cost?: number;
}

export interface Artifact {
    id: string;
    type: 'image' | 'file' | 'code_output' | 'chart';
    name: string;
    url: string;
    preview_url?: string;
    mime_type?: string;
    size_bytes?: number;
}

// Store for all responses by chat ID
export const responsesByChat: Writable<Record<string, Response[]>> = writable({});

// Store for currently streaming responses
export const streamingResponses: Writable<Record<string, Response>> = writable({});

// Add a response to a chat
export function addResponse(chatId: string, response: Response) {
    responsesByChat.update(byChat => {
        const existing = byChat[chatId] || [];
        return {
            ...byChat,
            [chatId]: [...existing, response]
        };
    });
}

// Update a response
export function updateResponse(chatId: string, responseId: string, updates: Partial<Response>) {
    responsesByChat.update(byChat => {
        const chatResponses = byChat[chatId] || [];
        const index = chatResponses.findIndex(r => r.id === responseId);

        if (index !== -1) {
            chatResponses[index] = {
                ...chatResponses[index],
                ...updates
            };
        }

        return {
            ...byChat,
            [chatId]: [...chatResponses]
        };
    });
}

// Append to output text (for streaming)
export function appendOutputText(chatId: string, responseId: string, text: string) {
    responsesByChat.update(byChat => {
        const chatResponses = byChat[chatId] || [];
        const index = chatResponses.findIndex(r => r.id === responseId);

        if (index !== -1) {
            chatResponses[index] = {
                ...chatResponses[index],
                output_text: (chatResponses[index].output_text || '') + text
            };
        }

        return {
            ...byChat,
            [chatId]: [...chatResponses]
        };
    });
}

// Add or update a tool call
export function updateToolCall(chatId: string, responseId: string, toolCall: ToolCall) {
    responsesByChat.update(byChat => {
        const chatResponses = byChat[chatId] || [];
        const responseIndex = chatResponses.findIndex(r => r.id === responseId);

        if (responseIndex !== -1) {
            const response = chatResponses[responseIndex];
            const toolIndex = response.tool_calls.findIndex(t => t.id === toolCall.id);

            if (toolIndex !== -1) {
                response.tool_calls[toolIndex] = toolCall;
            } else {
                response.tool_calls.push(toolCall);
            }

            chatResponses[responseIndex] = { ...response };
        }

        return {
            ...byChat,
            [chatId]: [...chatResponses]
        };
    });
}

// Get responses for a chat
export function getResponses(chatId: string): Readable<Response[]> {
    return derived(responsesByChat, $byChat => $byChat[chatId] || []);
}

// Get total cost for a chat
export function getChatCost(chatId: string): Readable<number> {
    return derived(responsesByChat, $byChat => {
        const responses = $byChat[chatId] || [];
        return responses.reduce((sum, r) => sum + (r.costs?.total || 0), 0);
    });
}
```

---

This provides the complete frontend component library for native Responses API support!
