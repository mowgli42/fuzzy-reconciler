<script>
  import { onMount } from 'svelte'
  import ResultsMap from './lib/ResultsMap.svelte'
  import DetailPanel from './lib/DetailPanel.svelte'
  import {
    CLASS_COLORS,
    CLASS_LABELS,
    defaultConfig,
    fetchDemo,
    fetchPresets,
    runCompare,
  } from './lib/api.js'

  let step = $state('ingest') // ingest | config | results | master
  let loading = $state(false)
  let error = $state('')
  let listA = $state([])
  let listB = $state([])
  let meta = $state({})
  let presets = $state([])
  let activePreset = $state('facility-loose')
  let config = $state(defaultConfig())
  let result = $state(null)
  let selectedId = $state(null)
  let filterClasses = $state([])
  let search = $state('')
  let decisions = $state({}) // pair_id -> { action, notes, at }
  let master = $state([])

  onMount(async () => {
    try {
      presets = await fetchPresets()
    } catch (e) {
      console.warn(e)
    }
  })

  async function loadDemo() {
    loading = true
    error = ''
    try {
      const data = await fetchDemo()
      listA = data.list_a
      listB = data.list_b
      meta = data.meta || {}
      step = 'config'
    } catch (e) {
      error = String(e.message || e)
    } finally {
      loading = false
    }
  }

  function applyPreset(id) {
    activePreset = id
    const p = presets.find((x) => x.id === id)
    if (p?.config) {
      config = structuredClone(p.config)
    }
  }

  async function compare() {
    loading = true
    error = ''
    try {
      result = await runCompare(listA, listB, config)
      selectedId = null
      filterClasses = []
      step = 'results'
    } catch (e) {
      error = String(e.message || e)
    } finally {
      loading = false
    }
  }

  let selectedPair = $derived(result?.matches?.find((m) => m.pair_id === selectedId) ?? null)

  let filteredMatches = $derived.by(() => {
    if (!result) return []
    let rows = result.matches.map((m) => {
      const d = decisions[m.pair_id]
      return d ? { ...m, classification: mapAction(d.action), notes: d.notes } : m
    })
    if (filterClasses.length) rows = rows.filter((m) => filterClasses.includes(m.classification))
    if (search.trim()) {
      const q = search.toLowerCase()
      rows = rows.filter(
        (m) =>
          (m.entity_a.name || '').toLowerCase().includes(q) ||
          (m.entity_b.name || '').toLowerCase().includes(q) ||
          m.classification.includes(q),
      )
    }
    return rows
  })

  function mapAction(action) {
    if (action === 'confirm_match') return 'confirmed_match'
    if (action === 'confirm_temporal') return 'confirmed_temporal'
    if (action === 'mark_distinct') return 'marked_distinct'
    return action
  }

  function toggleClass(c) {
    if (filterClasses.includes(c)) filterClasses = filterClasses.filter((x) => x !== c)
    else filterClasses = [...filterClasses, c]
  }

  function decide(pairId, action, notes) {
    const pair = result.matches.find((m) => m.pair_id === pairId)
    if (!pair) return
    const at = new Date().toISOString()
    decisions = { ...decisions, [pairId]: { action, notes, at } }
    if (action !== 'mark_distinct') {
      const merged = {
        id: pair.entity_a.id,
        name: pair.entity_a.name || pair.entity_b.name,
        lat: pair.entity_a.lat,
        lon: pair.entity_a.lon,
        analyzed_at: pair.entity_b.analyzed_at || pair.entity_a.analyzed_at,
        category: pair.entity_a.category || pair.entity_b.category,
        attributes: { ...pair.entity_a.attributes, ...pair.entity_b.attributes },
        _match_classification: mapAction(action),
        _composite_score: pair.scores.composite_score,
        _source_lists: 'A+B',
        _pair_id: pairId,
        _notes: notes,
        _decided_at: at,
        _name_a: pair.entity_a.name,
        _name_b: pair.entity_b.name,
        _geo_distance_m: pair.scores.geo_distance_m,
        _date_diff_days: pair.scores.date_diff_days,
      }
      master = [...master.filter((x) => x._pair_id !== pairId), merged]
    } else {
      master = master.filter((x) => x._pair_id !== pairId)
    }
  }

  function exportMasterCsv() {
    if (!master.length) return
    const cols = Object.keys(master[0])
    const lines = [cols.join(',')]
    for (const row of master) {
      lines.push(cols.map((c) => csvEscape(row[c])).join(','))
    }
    downloadText(lines.join('\n'), 'reconciled-master.csv', 'text/csv')
  }

  function exportResultsJson() {
    if (!result) return
    const payload = {
      summary: result.summary,
      config: result.config,
      matches: filteredMatches,
      decisions,
      master,
      exported_at: new Date().toISOString(),
    }
    downloadText(JSON.stringify(payload, null, 2), 'fuzzy-reconciler-results.json', 'application/json')
  }

  function csvEscape(v) {
    if (v == null) return ''
    const s = typeof v === 'object' ? JSON.stringify(v) : String(v)
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`
    return s
  }

  function downloadText(text, filename, type) {
    const blob = new Blob([text], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  function kpiEntries(counts) {
    const order = [
      'exact_match',
      'strong_fuzzy_match',
      'temporal_variant',
      'spatial_proximity_candidate',
      'weak_candidate',
      'ambiguous',
      'unmatched_a',
      'unmatched_b',
    ]
    return order
      .filter((k) => counts[k] != null)
      .map((k) => ({ key: k, count: counts[k], label: CLASS_LABELS[k] || k.replace(/_/g, ' '), color: CLASS_COLORS[k] || '#7a93a0' }))
  }

  function previewRows(list) {
    return list.slice(0, 6)
  }
</script>

<div class="shell">
  <header class="top">
    <div class="brand rise">
      <div class="mark" aria-hidden="true"></div>
      <div>
        <h1>Fuzzy Reconciler</h1>
        <p>Temporal variants · spatial proximity · auditable merge</p>
      </div>
    </div>
    <nav class="steps">
      {#each [['ingest', 'Ingest'], ['config', 'Configure'], ['results', 'Results'], ['master', 'Master']] as [id, label]}
        <button class:active={step === id} onclick={() => (step = id)} disabled={id !== 'ingest' && !listA.length}>
          {label}
        </button>
      {/each}
    </nav>
  </header>

  {#if error}
    <div class="error" role="alert">{error}</div>
  {/if}

  {#if step === 'ingest'}
    <section class="ingest rise">
      <div class="hero-copy">
        <h2>Compare two entity lists that should have stayed linked</h2>
        <p>
          Load controlled demo POIs around the Space Coast AO — exact matches, temporal updates, and nearby facilities with name drift.
        </p>
        <button class="cta pulse-cta" onclick={loadDemo} disabled={loading}>
          {loading ? 'Loading…' : 'Load Demo Data'}
        </button>
      </div>
      <div class="drop-grid">
        <div class="drop">
          <h3>List A</h3>
          <p class="muted">{listA.length ? `${listA.length} entities ready` : 'CSV / JSON upload next — demo bypasses mapping'}</p>
          {#if listA.length}
            <table>
              <thead><tr><th>name</th><th>category</th><th>lat</th></tr></thead>
              <tbody>
                {#each previewRows(listA) as row}
                  <tr><td>{row.name}</td><td>{row.category}</td><td class="mono">{row.lat?.toFixed?.(4) ?? row.lat}</td></tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
        <div class="drop">
          <h3>List B</h3>
          <p class="muted">{listB.length ? `${listB.length} entities ready` : 'Awaiting second list'}</p>
          {#if listB.length}
            <table>
              <thead><tr><th>name</th><th>category</th><th>lat</th></tr></thead>
              <tbody>
                {#each previewRows(listB) as row}
                  <tr><td>{row.name}</td><td>{row.category}</td><td class="mono">{row.lat?.toFixed?.(4) ?? row.lat}</td></tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
      </div>
      {#if listA.length}
        <div class="footer-actions">
          <span class="muted mono">{meta.counts ? `A=${meta.counts.list_a} · B=${meta.counts.list_b}` : ''}</span>
          <button class="primary" onclick={() => (step = 'config')}>Continue to Configuration</button>
        </div>
      {/if}
    </section>
  {/if}

  {#if step === 'config'}
    <section class="config rise">
      <div class="config-main">
        <h2>Matching parameters</h2>
        <div class="presets">
          {#each presets as p}
            <button class:on={activePreset === p.id} onclick={() => applyPreset(p.id)}>{p.name}</button>
          {/each}
        </div>
        <div class="sliders">
          <label>Geo distance (m)
            <input type="range" min="50" max="2000" step="10" bind:value={config.max_geo_distance_m} />
            <span class="mono">{config.max_geo_distance_m}</span>
          </label>
          <label>Min name similarity (%)
            <input type="range" min="0" max="100" bind:value={config.min_name_similarity} />
            <span class="mono">{config.min_name_similarity}</span>
          </label>
          <label>Min attr similarity
            <input type="range" min="0" max="1" step="0.01" bind:value={config.min_attr_similarity} />
            <span class="mono">{Number(config.min_attr_similarity).toFixed(2)}</span>
          </label>
          <label>Date tolerance (days)
            <input type="range" min="0" max="90" bind:value={config.date_tolerance_days} />
            <span class="mono">{config.date_tolerance_days}</span>
          </label>
          <label>Composite threshold
            <input type="range" min="0.4" max="0.99" step="0.01" bind:value={config.composite_threshold} />
            <span class="mono">{Number(config.composite_threshold).toFixed(2)}</span>
          </label>
        </div>
        <h3>Weights</h3>
        <div class="weights">
          {#each ['geo', 'name', 'attr', 'temporal'] as w}
            <label>{w}
              <input type="range" min="0" max="1" step="0.01" bind:value={config.weights[w]} />
              <span class="mono">{Number(config.weights[w]).toFixed(2)}</span>
            </label>
          {/each}
        </div>
      </div>
      <aside class="config-side">
        <p>Demo lists loaded with intentional temporal variants and spatial proximity candidates. Facility Loose is a good first preset for screenshots.</p>
        <button class="cta pulse-cta" onclick={compare} disabled={loading}>
          {loading ? 'Comparing…' : 'Run Fuzzy Comparison'}
        </button>
        <button class="ghost-link" onclick={() => (step = 'ingest')}>← Back to ingest</button>
      </aside>
    </section>
  {/if}

  {#if step === 'results' && result}
    <section class="results">
      <div class="kpis rise">
        {#each kpiEntries(result.summary.counts) as k}
          <button class="kpi" style="--c: {k.color}" onclick={() => toggleClass(k.key.startsWith('unmatched') ? 'unmatched' : k.key)}>
            <span class="kpi-count">{k.count}</span>
            <span class="kpi-label">{k.label}</span>
          </button>
        {/each}
        <div class="kpi meta-kpi">
          <span class="kpi-count mono">{result.summary.elapsed_ms?.toFixed?.(0) ?? '—'}ms</span>
          <span class="kpi-label">engine</span>
        </div>
      </div>

      <div class="toolbar">
        <input type="search" placeholder="Search names…" bind:value={search} />
        <div class="chips">
          {#each ['exact_match', 'strong_fuzzy_match', 'temporal_variant', 'spatial_proximity_candidate', 'weak_candidate'] as c}
            <button class:on={filterClasses.includes(c)} onclick={() => toggleClass(c)}>
              <span class="dot" style="background:{CLASS_COLORS[c]}"></span>
              {CLASS_LABELS[c]}
            </button>
          {/each}
        </div>
        <div class="toolbar-actions">
          <button onclick={compare} disabled={loading}>Re-run</button>
          <button onclick={() => (step = 'master')}>Master ({master.length})</button>
          <button onclick={exportResultsJson}>Export JSON</button>
        </div>
      </div>

      <div class="workspace" class:with-detail={!!selectedPair}>
        <div class="table-wrap rise">
          <table>
            <thead>
              <tr>
                <th>Class</th>
                <th>%</th>
                <th>Geo m</th>
                <th>Name</th>
                <th>Date Δ</th>
                <th>A</th>
                <th>B</th>
              </tr>
            </thead>
            <tbody>
              {#each filteredMatches as m}
                <tr class:selected={selectedId === m.pair_id} onclick={() => (selectedId = m.pair_id)}>
                  <td><span class="badge badge-{m.classification}">{CLASS_LABELS[m.classification] || m.classification}</span></td>
                  <td class="mono">{(m.scores.composite_score * 100).toFixed(0)}</td>
                  <td class="mono">{m.scores.geo_distance_m?.toFixed?.(0) ?? '—'}</td>
                  <td class="mono">{m.scores.name_similarity_pct?.toFixed?.(0) ?? '—'}%</td>
                  <td class="mono">{m.scores.date_diff_days?.toFixed?.(0) ?? '—'}</td>
                  <td>{m.entity_a.name}</td>
                  <td>{m.entity_b.name}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="map-pane rise">
          <ResultsMap
            matches={result.matches}
            unmatchedA={result.unmatched_a}
            unmatchedB={result.unmatched_b}
            {selectedId}
            activeClasses={filterClasses}
            onselect={(id) => (selectedId = id)}
          />
        </div>
        {#if selectedPair}
          <div class="detail-pane">
            <DetailPanel
              pair={selectedPair}
              ondecide={decide}
              onclose={() => (selectedId = null)}
            />
          </div>
        {/if}
      </div>
    </section>
  {/if}

  {#if step === 'master'}
    <section class="master rise">
      <div class="master-head">
        <h2>Reconciled master</h2>
        <div class="toolbar-actions">
          <button class="primary" onclick={exportMasterCsv} disabled={!master.length}>Download CSV</button>
          <button onclick={exportResultsJson}>Full package JSON</button>
          <button onclick={() => (step = 'results')}>← Results</button>
        </div>
      </div>
      {#if !master.length}
        <p class="muted">Confirm matches from the detail panel to build the master list.</p>
      {:else}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Class</th>
              <th>Score</th>
              <th>Notes</th>
              <th>Decided</th>
            </tr>
          </thead>
          <tbody>
            {#each master as row}
              <tr>
                <td>{row.name}</td>
                <td><span class="badge badge-{row._match_classification}">{CLASS_LABELS[row._match_classification]}</span></td>
                <td class="mono">{(row._composite_score * 100).toFixed(0)}%</td>
                <td>{row._notes || '—'}</td>
                <td class="mono">{row._decided_at}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    </section>
  {/if}
</div>

<style>
  .shell {
    max-width: 1400px;
    margin: 0 auto;
    padding: 1.25rem 1.5rem 2.5rem;
  }
  .top {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-end;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid var(--line);
    padding-bottom: 1rem;
  }
  .brand {
    display: flex;
    gap: 0.85rem;
    align-items: center;
  }
  .mark {
    width: 42px;
    height: 42px;
    border-radius: 6px;
    background:
      radial-gradient(circle at 30% 40%, var(--teal) 0 28%, transparent 30%),
      radial-gradient(circle at 70% 62%, var(--amber) 0 26%, transparent 28%),
      linear-gradient(145deg, #143443, #0b1f2a);
    border: 1px solid var(--line);
  }
  h1 {
    margin: 0;
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--paper);
  }
  .brand p {
    margin: 0.15rem 0 0;
    font-size: 0.85rem;
    color: var(--paper-dim);
  }
  .steps {
    display: flex;
    gap: 0.35rem;
  }
  .steps button {
    background: transparent;
    border: 1px solid var(--line);
    color: var(--paper-dim);
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    font-size: 0.78rem;
  }
  .steps button.active {
    border-color: var(--teal);
    color: var(--teal);
    background: rgba(46, 196, 182, 0.08);
  }
  .steps button:disabled {
    opacity: 0.35;
  }
  .error {
    background: rgba(196, 69, 54, 0.15);
    border: 1px solid rgba(196, 69, 54, 0.4);
    color: #f0b4ad;
    padding: 0.6rem 0.8rem;
    border-radius: 4px;
    margin-bottom: 1rem;
  }
  .ingest .hero-copy {
    max-width: 40rem;
    margin-bottom: 1.5rem;
  }
  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.35rem;
  }
  .hero-copy p {
    color: var(--paper-dim);
    line-height: 1.45;
  }
  .cta {
    margin-top: 1rem;
    background: var(--teal);
    color: var(--ink);
    border: none;
    font-weight: 700;
    padding: 0.7rem 1.2rem;
    border-radius: 4px;
    font-size: 0.95rem;
  }
  .cta:disabled {
    opacity: 0.6;
  }
  .drop-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }
  @media (max-width: 800px) {
    .drop-grid {
      grid-template-columns: 1fr;
    }
  }
  .drop {
    background: rgba(16, 40, 51, 0.75);
    border: 1px dashed var(--line);
    border-radius: 6px;
    padding: 1rem;
    min-height: 180px;
  }
  .drop h3 {
    margin: 0 0 0.35rem;
    font-size: 0.9rem;
    color: var(--teal);
  }
  .muted {
    color: var(--gray);
    font-size: 0.85rem;
  }
  .mono {
    font-family: var(--font-mono);
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
    margin-top: 0.6rem;
  }
  th,
  td {
    text-align: left;
    padding: 0.35rem 0.4rem;
    border-bottom: 1px solid rgba(42, 74, 87, 0.55);
  }
  th {
    color: var(--gray);
    font-weight: 500;
    font-family: var(--font-mono);
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .footer-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 1rem;
  }
  .primary {
    background: var(--teal);
    color: var(--ink);
    border: none;
    font-weight: 650;
    padding: 0.55rem 0.9rem;
    border-radius: 4px;
  }
  .config {
    display: grid;
    grid-template-columns: 1.4fr 0.8fr;
    gap: 1.25rem;
  }
  @media (max-width: 900px) {
    .config {
      grid-template-columns: 1fr;
    }
  }
  .config-main,
  .config-side {
    background: rgba(16, 40, 51, 0.8);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 1.1rem;
  }
  .presets {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin: 0.8rem 0 1rem;
  }
  .presets button {
    background: transparent;
    border: 1px solid var(--line);
    color: var(--paper-dim);
    border-radius: 999px;
    padding: 0.3rem 0.7rem;
    font-size: 0.78rem;
  }
  .presets button.on {
    border-color: var(--amber);
    color: var(--amber);
  }
  .sliders,
  .weights {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }
  .sliders label,
  .weights label {
    display: grid;
    grid-template-columns: 1fr 1.2fr 3rem;
    gap: 0.5rem;
    align-items: center;
    font-size: 0.82rem;
  }
  input[type='range'] {
    width: 100%;
    accent-color: var(--teal);
  }
  .config-side p {
    color: var(--paper-dim);
    line-height: 1.45;
    font-size: 0.9rem;
  }
  .ghost-link {
    display: inline-block;
    margin-top: 0.8rem;
    background: none;
    border: none;
    color: var(--gray);
    padding: 0;
  }
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
    gap: 0.5rem;
    margin-bottom: 0.85rem;
  }
  .kpi {
    background: rgba(16, 40, 51, 0.85);
    border: 1px solid var(--line);
    border-left: 3px solid var(--c, var(--line));
    border-radius: 4px;
    padding: 0.55rem 0.65rem;
    text-align: left;
    color: inherit;
  }
  .kpi-count {
    display: block;
    font-family: var(--font-mono);
    font-size: 1.25rem;
    font-weight: 600;
  }
  .kpi-label {
    font-size: 0.7rem;
    color: var(--gray);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    align-items: center;
    margin-bottom: 0.75rem;
  }
  .toolbar input[type='search'] {
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid var(--line);
    color: var(--paper);
    border-radius: 4px;
    padding: 0.4rem 0.6rem;
    min-width: 180px;
  }
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
    flex: 1;
  }
  .chips button {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    background: transparent;
    border: 1px solid var(--line);
    color: var(--paper-dim);
    border-radius: 999px;
    padding: 0.2rem 0.55rem;
    font-size: 0.72rem;
  }
  .chips button.on {
    border-color: var(--teal);
    color: var(--paper);
  }
  .dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
  }
  .toolbar-actions {
    display: flex;
    gap: 0.35rem;
  }
  .toolbar-actions button {
    background: rgba(16, 40, 51, 0.9);
    border: 1px solid var(--line);
    color: var(--paper);
    border-radius: 4px;
    padding: 0.35rem 0.6rem;
    font-size: 0.75rem;
  }
  .workspace {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    grid-template-rows: minmax(420px, 62vh);
    gap: 0.75rem;
  }
  .workspace.with-detail {
    grid-template-columns: 1fr 0.95fr 0.95fr;
  }
  @media (max-width: 1100px) {
    .workspace,
    .workspace.with-detail {
      grid-template-columns: 1fr;
      grid-template-rows: auto;
    }
    .map-pane {
      min-height: 360px;
    }
  }
  .table-wrap {
    overflow: auto;
    background: rgba(16, 40, 51, 0.75);
    border: 1px solid var(--line);
    border-radius: 6px;
  }
  .table-wrap tr {
    cursor: pointer;
  }
  .table-wrap tr.selected,
  .table-wrap tr:hover {
    background: rgba(46, 196, 182, 0.08);
  }
  .map-pane {
    min-height: 100%;
  }
  .master-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .master {
    background: rgba(16, 40, 51, 0.75);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 1rem;
  }
</style>
