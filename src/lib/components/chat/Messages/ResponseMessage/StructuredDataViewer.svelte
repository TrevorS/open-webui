<script lang="ts">
	import { toast } from 'svelte-sonner';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';

	export let data: Record<string, any> = {};
	export let toolName: string = 'Tool';

	let expanded = false;

	const copyToClipboard = async () => {
		try {
			await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
			toast.success('Copied to clipboard');
		} catch (error) {
			toast.error('Failed to copy');
		}
	};

	const formatValue = (value: any): string => {
		if (value === null) return 'null';
		if (typeof value === 'string') return `"${value}"`;
		if (typeof value === 'boolean') return value ? 'true' : 'false';
		if (typeof value === 'number') return String(value);
		return JSON.stringify(value);
	};
</script>

<div class="my-2 w-full max-w-2xl rounded-lg bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800 overflow-hidden">
	<!-- Header -->
	<div class="flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
		<button
			on:click={() => (expanded = !expanded)}
			class="flex items-center gap-2 font-medium text-sm text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
		>
			<div class="w-5 h-5 transform transition-transform {expanded ? 'rotate-180' : ''}">
				<ChevronDown />
			</div>
			<span>{toolName} Data</span>
		</button>
		<button
			on:click={copyToClipboard}
			class="px-2 py-1 rounded text-xs font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
			title="Copy JSON"
		>
			Copy
		</button>
	</div>

	<!-- Content -->
	{#if expanded}
		<div class="px-4 py-3 max-h-96 overflow-y-auto font-mono text-sm text-gray-700 dark:text-gray-300">
			{#each Object.entries(data) as [key, value]}
				<div class="mb-2">
					<span class="font-semibold text-blue-600 dark:text-blue-400">"{key}"</span>
					<span class="text-gray-500 dark:text-gray-400">:</span>
					{#if typeof value === 'object' && value !== null}
						<span class="text-gray-500 dark:text-gray-400">
							{Array.isArray(value) ? '[...]' : '{...}'}
						</span>
						<div class="ml-4 text-xs text-gray-500 dark:text-gray-400">
							{#if Array.isArray(value)}
								Array of {value.length} item{value.length !== 1 ? 's' : ''}
							{:else}
								Object with {Object.keys(value).length} property(ies)
							{/if}
						</div>
						{#if Array.isArray(value) && value.length > 0}
							<details class="ml-2 text-xs">
								<summary class="cursor-pointer text-blue-600 dark:text-blue-400 hover:underline">
									View items
								</summary>
								<div class="ml-2 mt-1 text-gray-600 dark:text-gray-400">
									{#each value as item, idx}
										<div>
											[{idx}]
											{#if typeof item === 'object' && item !== null}
												{JSON.stringify(item)}
											{:else}
												{formatValue(item)}
											{/if}
										</div>
									{/each}
								</div>
							</details>
						{/if}
						{#if typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0}
							<details class="ml-2 text-xs">
								<summary class="cursor-pointer text-blue-600 dark:text-blue-400 hover:underline">
									View properties
								</summary>
								<div class="ml-2 mt-1 text-gray-600 dark:text-gray-400">
									{#each Object.entries(value) as [subKey, subValue]}
										<div>
											"{subKey}": {formatValue(subValue)}
										</div>
									{/each}
								</div>
							</details>
						{/if}
					{:else}
						<span class="text-amber-600 dark:text-amber-400">{formatValue(value)}</span>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</div>
