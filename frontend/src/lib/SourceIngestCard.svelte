<script>
  let {
    label = 'Source',
    preview = null,
    onfile = () => {},
  } = $props()

  let inputEl

  const metrics = $derived(preview?.metrics)
  const rows = $derived(preview?.preview_rows || [])
  const cats = $derived(
    metrics?.categories
      ? Object.entries(metrics.categories)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 6)
      : [],
  )

  function onPick(e) {
    const file = e.target.files?.[0]
    if (file) onfile(file)
  }
</script>

<div class="drop" class:ready={!!preview?.row_count}>
  <div class="drop-head">
    <h3>{label}</h3>
    <button type="button" class="browse" onclick={() => inputEl?.click()}>Browse file</button>
    <input
      bind:this={inputEl}
      type="file"
      accept=".csv,.tsv,.txt,.json,.jsonl,.ndjson,.geojson,text/csv,application/json"
      onchange={onPick}
      hidden
    />
  </div>

  {#if !preview?.row_count}
    <p class="muted">
      CSV · TSV · JSON · JSONL · GeoJSON. Column aliases and light regex map headers (e.g. POI_Name → name,
      latitude → lat). Preview before advancing.
    </p>
  {:else}
    <div class="metrics" aria-label="{label} ingest metrics">
      <div><span class="m-label">Total rows</span><span class="m-val mono">{metrics.total_rows}</span></div>
      <div><span class="m-label">Columns</span><span class="m-val mono">{metrics.column_count}</span></div>
      <div><span class="m-label">Geo valid</span><span class="m-val mono">{metrics.geo_valid}</span></div>
      <div><span class="m-label">Geo missing</span><span class="m-val mono warn">{metrics.geo_missing}</span></div>
      <div><span class="m-label">Named</span><span class="m-val mono">{metrics.named}</span></div>
      <div><span class="m-label">Warnings</span><span class="m-val mono" class:warn={metrics.warning_count > 0}>{metrics.warning_count}</span></div>
    </div>

    <div class="meta-line mono">
      {preview.source_format || 'unknown'}
      {#if preview.source_filename}
        · {preview.source_filename}
      {/if}
      · showing {rows.length} of {preview.row_count}
    </div>

    {#if cats.length}
      <div class="cats">
        {#each cats as [c, n]}
          <span>{c} <strong class="mono">{n}</strong></span>
        {/each}
      </div>
    {/if}

    {#if preview.detected_mapping && Object.keys(preview.detected_mapping).length}
      <div class="mapping mono">
        map:
        {#each Object.entries(preview.detected_mapping) as [field, col], i}
          {field}←{col}{i < Object.keys(preview.detected_mapping).length - 1 ? '; ' : ''}
        {/each}
      </div>
    {/if}

    <div class="preview-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>id</th>
            <th>name</th>
            <th>category</th>
            <th>lat</th>
            <th>lon</th>
            <th>analyzed_at</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row, i}
            <tr>
              <td class="mono">{i + 1}</td>
              <td class="mono">{row.id ?? '—'}</td>
              <td>{row.name || '—'}</td>
              <td>{row.category || '—'}</td>
              <td class="mono">{row.lat != null ? Number(row.lat).toFixed(4) : '—'}</td>
              <td class="mono">{row.lon != null ? Number(row.lon).toFixed(4) : '—'}</td>
              <td class="mono">{row.analyzed_at ? String(row.analyzed_at).slice(0, 19) : '—'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if preview.validation_warnings?.length}
      <details class="warns">
        <summary>{preview.validation_warnings.length} validation notes</summary>
        <ul>
          {#each preview.validation_warnings.slice(0, 8) as w}
            <li>{w}</li>
          {/each}
        </ul>
      </details>
    {/if}
  {/if}
</div>

<style>
  .drop {
    background: rgba(16, 40, 51, 0.75);
    border: 1px dashed var(--line);
    border-radius: 6px;
    padding: 1rem;
    min-height: 220px;
  }
  .drop.ready {
    border-style: solid;
    border-color: rgba(42, 157, 143, 0.45);
  }
  .drop-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
  }
  h3 {
    margin: 0;
    font-size: 0.9rem;
    color: var(--teal);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .browse {
    background: transparent;
    border: 1px solid var(--line);
    color: var(--paper-dim);
    border-radius: 4px;
    padding: 0.25rem 0.55rem;
    font-size: 0.72rem;
  }
  .muted {
    color: var(--gray);
    font-size: 0.85rem;
    line-height: 1.4;
  }
  .metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.4rem;
    margin-bottom: 0.55rem;
  }
  .metrics > div {
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid rgba(42, 74, 87, 0.6);
    border-radius: 3px;
    padding: 0.35rem 0.45rem;
  }
  .m-label {
    display: block;
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--gray);
  }
  .m-val {
    font-size: 1rem;
    font-weight: 600;
  }
  .warn {
    color: #f0b4ad;
  }
  .mono {
    font-family: var(--font-mono);
  }
  .meta-line {
    font-size: 0.7rem;
    color: var(--gray);
    margin-bottom: 0.4rem;
  }
  .cats {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.45rem;
  }
  .cats span {
    font-size: 0.7rem;
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: 0.1rem 0.4rem;
    color: var(--paper-dim);
  }
  .mapping {
    font-size: 0.65rem;
    color: var(--gray);
    margin-bottom: 0.45rem;
    word-break: break-word;
  }
  .preview-wrap {
    max-height: 280px;
    overflow: auto;
    border: 1px solid rgba(42, 74, 87, 0.55);
    border-radius: 4px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.72rem;
    margin: 0;
  }
  th,
  td {
    text-align: left;
    padding: 0.28rem 0.35rem;
    border-bottom: 1px solid rgba(42, 74, 87, 0.45);
    white-space: nowrap;
  }
  th {
    position: sticky;
    top: 0;
    background: #102833;
    color: var(--gray);
    font-family: var(--font-mono);
    font-size: 0.62rem;
    text-transform: uppercase;
  }
  .warns {
    margin-top: 0.5rem;
    font-size: 0.75rem;
    color: #f0b4ad;
  }
  .warns ul {
    margin: 0.35rem 0 0;
    padding-left: 1.1rem;
  }
</style>
