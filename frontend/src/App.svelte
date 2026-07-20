<script>
  import { onMount } from 'svelte'
  import ResultsMap from './lib/ResultsMap.svelte'
  import DetailPanel from './lib/DetailPanel.svelte'
  import SourceIngestCard from './lib/SourceIngestCard.svelte'
  import {
    CLASS_COLORS,
    CLASS_LABELS,
    defaultConfig,
    fetchDemoIngestPreview,
    fetchPresets,
    ingestOneSide,
    runCompare,
  } from './lib/api.js'
  import { buildInventory } from './lib/inventory.js'
  import {
    declineTrendByCategory,
    findPriorDecline,
    loadDeclineLedger,
    recordDecline,
    removeDecline,
  } from './lib/ledger.js'
  import {
    clearSession,
    getPersistenceMode,
    loadSession,
    persistenceLabel,
    saveSession,
    setPersistenceMode,
  } from './lib/session.js'

  const STEPS = [
    { id: 'ingest', label: 'Ingest' },
    { id: 'config', label: 'Configure' },
    { id: 'results', label: 'Results' },
    { id: 'merge', label: 'Merge' },
  ]

  let step = $state('ingest')
  let loading = $state(false)
  let error = $state('')
  let listA = $state([])
  let listB = $state([])
  let previewA = $state(null)
  let previewB = $state(null)
  let meta = $state({})
  let pendingFileA = $state(null)
  let pendingFileB = $state(null)
  let presets = $state([])
  let activePreset = $state('facility-loose')
  let config = $state(defaultConfig())
  let result = $state(null)
  let selectedId = $state(null)
  let filterClasses = $state([])
  let search = $state('')
  let decisions = $state({})
  let workingSet = $state([])
  let declineLedger = $state([])
  let published = $state(false)
  let publishNote = $state('')
  let persistenceMode = $state('browser')

  function persistLite() {
    saveSession({
      step,
      activePreset,
      config,
      decisions,
      workingSet,
      published,
      publishNote,
      // previews/entities can be large — restore declines from ledger; re-load sample if needed
    })
  }

  onMount(async () => {
    persistenceMode = getPersistenceMode()
    declineLedger = loadDeclineLedger()
    const saved = loadSession()
    if (saved && persistenceMode === 'browser') {
      if (saved.config) config = saved.config
      if (saved.activePreset) activePreset = saved.activePreset
      if (saved.decisions) decisions = saved.decisions
      if (saved.workingSet) workingSet = saved.workingSet
      if (saved.published) published = saved.published
      if (saved.publishNote) publishNote = saved.publishNote
      if (saved.step && ['ingest', 'config', 'results', 'merge'].includes(saved.step)) {
        // Don't jump to results without entities — stay ingest unless we have working merge context
        if (saved.step === 'merge' || saved.step === 'results') step = saved.workingSet?.length ? 'merge' : 'ingest'
        else step = saved.step === 'config' ? 'ingest' : saved.step
      }
    }
    try {
      presets = await fetchPresets()
    } catch (e) {
      console.warn(e)
    }
  })

  $effect(() => {
    // autosave lightweight session when browser persistence is on
    decisions
    workingSet
    published
    config
    activePreset
    if (typeof window !== 'undefined') persistLite()
  })

  function togglePersistence() {
    const next = persistenceMode === 'browser' ? 'none' : 'browser'
    setPersistenceMode(next)
    persistenceMode = next
    if (next === 'none') clearSession()
  }

  function clearLocalHistory() {
    clearSession()
    declineLedger = []
    localStorage.removeItem('fr-decline-ledger-v1')
    decisions = {}
    workingSet = []
    published = false
    publishNote = ''
  }

  let ingestReady = $derived(
    !!previewA?.row_count &&
      !!previewB?.row_count &&
      (previewA.metrics?.geo_valid ?? 0) > 0 &&
      (previewB.metrics?.geo_valid ?? 0) > 0,
  )

  let stepComplete = $derived({
    ingest: ingestReady,
    config: !!result,
    results: Object.keys(decisions).length > 0 || published,
    merge: published,
  })

  let pendingCount = $derived(
    result ? result.matches.filter((m) => !decisions[m.pair_id]).length : 0,
  )

  let decidedCount = $derived(Object.keys(decisions).length)

  let keepSeparateCount = $derived(
    Object.values(decisions).filter((d) => d.action === 'keep_separate').length,
  )

  let inventory = $derived(
    buildInventory({
      listA,
      listB,
      matches: result?.matches || [],
      decisions,
      workingSet,
    }),
  )

  let declineTrend = $derived(declineTrendByCategory(declineLedger))

  let selectedPair = $derived(result?.matches?.find((m) => m.pair_id === selectedId) ?? null)

  let selectedPrior = $derived(
    selectedPair ? findPriorDecline(selectedPair, declineLedger) : null,
  )

  let filteredMatches = $derived.by(() => {
    if (!result) return []
    let rows = result.matches.map((m) => {
      const d = decisions[m.pair_id]
      const prior = findPriorDecline(m, declineLedger)
      return d
        ? { ...m, classification: mapAction(d.action), notes: d.notes, priorDecline: prior }
        : { ...m, priorDecline: prior }
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

  function stepStatus(id) {
    if (step === id) return 'active'
    if (stepComplete[id]) return 'complete'
    return 'pending'
  }

  function canOpenStep(id) {
    if (id === 'ingest') return true
    if (id === 'config') return stepComplete.ingest
    if (id === 'results') return !!result
    if (id === 'merge') return !!result
    return false
  }

  function applyPreviewPayload(data) {
    previewA = data.list_a
    previewB = data.list_b
    listA = data.list_a.entities || []
    listB = data.list_b.entities || []
    meta = {
      counts: { list_a: data.list_a.row_count, list_b: data.list_b.row_count },
      formats: {
        a: data.list_a.source_format,
        b: data.list_b.source_format,
      },
    }
    published = false
    decisions = {}
    workingSet = []
    result = null
  }

  async function loadSample() {
    loading = true
    error = ''
    try {
      const data = await fetchDemoIngestPreview()
      applyPreviewPayload(data)
      pendingFileA = null
      pendingFileB = null
      step = 'ingest'
    } catch (e) {
      error = String(e.message || e)
    } finally {
      loading = false
    }
  }

  async function onSourceFile(side, file) {
    loading = true
    error = ''
    try {
      const data = await ingestOneSide(side, file)
      if (side === 'A') {
        previewA = data.list_a
        listA = data.list_a.entities || []
        pendingFileA = file
      } else {
        previewB = data.list_b
        listB = data.list_b.entities || []
        pendingFileB = file
      }
      meta = {
        counts: {
          list_a: previewA?.row_count || 0,
          list_b: previewB?.row_count || 0,
        },
        formats: {
          a: previewA?.source_format,
          b: previewB?.source_format,
        },
      }
      published = false
      decisions = {}
      workingSet = []
      result = null
      step = 'ingest'
    } catch (e) {
      error = String(e.message || e)
    } finally {
      loading = false
    }
  }

  function applyPreset(id) {
    activePreset = id
    const p = presets.find((x) => x.id === id)
    if (p?.config) config = structuredClone(p.config)
  }

  async function compare() {
    loading = true
    error = ''
    try {
      result = await runCompare(listA, listB, config)
      selectedId = null
      filterClasses = []
      published = false
      step = 'results'
    } catch (e) {
      error = String(e.message || e)
    } finally {
      loading = false
    }
  }

  function mapAction(action) {
    if (action === 'confirm_match') return 'confirmed_match'
    if (action === 'confirm_temporal') return 'confirmed_temporal'
    if (action === 'keep_separate' || action === 'mark_distinct') return 'marked_distinct'
    return action
  }

  function toggleClass(c) {
    if (filterClasses.includes(c)) filterClasses = filterClasses.filter((x) => x !== c)
    else filterClasses = [...filterClasses, c]
  }

  function commitDisposition(pairId, action, notes) {
    const pair = result.matches.find((m) => m.pair_id === pairId)
    if (!pair) return
    const at = new Date().toISOString()
    const normalized = action === 'mark_distinct' ? 'keep_separate' : action
    decisions = { ...decisions, [pairId]: { action: normalized, notes, at } }

    if (normalized === 'keep_separate') {
      declineLedger = recordDecline(pair, notes)
      workingSet = workingSet.filter((x) => x._pair_id !== pairId)
    } else {
      declineLedger = removeDecline(pair)
      const merged = {
        id: pair.entity_a.id,
        name: pair.entity_a.name || pair.entity_b.name,
        lat: pair.entity_a.lat,
        lon: pair.entity_a.lon,
        analyzed_at: pair.entity_b.analyzed_at || pair.entity_a.analyzed_at,
        category: pair.entity_a.category || pair.entity_b.category,
        attributes: { ...pair.entity_a.attributes, ...pair.entity_b.attributes },
        _match_classification: mapAction(normalized),
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
      workingSet = [...workingSet.filter((x) => x._pair_id !== pairId), merged]
    }
  }

  function goMerge() {
    step = 'merge'
  }

  function publishWorkingSet() {
    published = true
    publishNote = `Published ${new Date().toLocaleString()} · ${workingSet.length} merged · ${keepSeparateCount} kept separate`
  }

  function exportWorkingCsv() {
    if (!workingSet.length) return
    const cols = Object.keys(workingSet[0])
    const lines = [cols.join(',')]
    for (const row of workingSet) {
      lines.push(cols.map((c) => csvEscape(row[c])).join(','))
    }
    downloadText(lines.join('\n'), 'working-merge-set.csv', 'text/csv')
  }

  function exportPackage() {
    if (!result) return
    const payload = {
      summary: result.summary,
      config: result.config,
      inventory,
      matches: filteredMatches,
      decisions,
      working_set: workingSet,
      decline_ledger: declineLedger,
      published,
      exported_at: new Date().toISOString(),
    }
    downloadText(JSON.stringify(payload, null, 2), 'reconcile-package.json', 'application/json')
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
      .map((k) => ({
        key: k,
        count: counts[k],
        label: CLASS_LABELS[k] || k.replace(/_/g, ' '),
        color: CLASS_COLORS[k] || '#7a93a0',
      }))
  }

  function flagLabel(flag) {
    if (flag === 'inflation') return 'Over-count risk'
    if (flag === 'deflation') return 'Under-merge'
    if (flag === 'watch') return 'Watch'
    return ''
  }
</script>

<div class="shell">
  <header class="top">
    <div class="brand rise">
      <div class="mark" aria-hidden="true"></div>
      <div>
        <h1>Fuzzy Reconciler</h1>
        <p>Operational entity reconciliation · temporal · spatial · auditable merge</p>
      </div>
    </div>
    <nav class="steps" aria-label="Workflow progress">
      {#each STEPS as s}
        <button
          class="step"
          class:active={stepStatus(s.id) === 'active'}
          class:complete={stepStatus(s.id) === 'complete'}
          class:pending={stepStatus(s.id) === 'pending'}
          onclick={() => canOpenStep(s.id) && (step = s.id)}
          disabled={!canOpenStep(s.id)}
        >
          <span class="step-dot" aria-hidden="true"></span>
          {s.label}
        </button>
      {/each}
    </nav>
  </header>

  <div class="persist-banner" role="note">
    <span>
      <strong>Demo persistence:</strong> {persistenceLabel(persistenceMode)}.
      Server is stateless — no shared database. Shared multi-user history is optional later.
    </span>
    <div class="persist-actions">
      <button type="button" onclick={togglePersistence}>
        {persistenceMode === 'browser' ? 'Disable browser cache' : 'Enable browser cache'}
      </button>
      <button type="button" onclick={clearLocalHistory}>Clear local history</button>
    </div>
  </div>

  {#if error}
    <div class="error" role="alert">{error}</div>
  {/if}

  {#if step === 'ingest'}
    <section class="ingest rise">
      <div class="hero-copy">
        <h2>Ingest and verify source lists</h2>
        <p>
          Stage Source A and Source B, then inspect totals and the first rows before any comparison.
          Supported today: CSV, TSV, JSON, JSONL, GeoJSON with alias + light regex header mapping — not
          full custom regex importers (those can be added as mapping presets later).
        </p>
        <button class="cta pulse-cta" onclick={loadSample} disabled={loading}>
          {loading ? 'Loading…' : 'Load sample inventories'}
        </button>
      </div>

      <div class="drop-grid">
        <SourceIngestCard label="Source A" preview={previewA} onfile={(f) => onSourceFile('A', f)} />
        <SourceIngestCard label="Source B" preview={previewB} onfile={(f) => onSourceFile('B', f)} />
      </div>

      {#if previewA?.row_count || previewB?.row_count}
        <div class="verify-bar">
          <div>
            <strong>Verification</strong>
            <p class="muted">
              A: {previewA?.row_count || 0} rows
              ({previewA?.metrics?.geo_valid ?? 0} geo-valid) ·
              B: {previewB?.row_count || 0} rows
              ({previewB?.metrics?.geo_valid ?? 0} geo-valid)
              {#if !ingestReady}
                — both sides need geo-valid rows before Configure
              {/if}
            </p>
          </div>
          <button class="primary" disabled={!ingestReady} onclick={() => (step = 'config')}>
            Data looks correct — advance to Configure
          </button>
        </div>
      {/if}
    </section>
  {/if}

  {#if step === 'config'}
    <section class="config rise">
      <div class="config-main">
        <h2>Matching thresholds</h2>
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
        <h3>Score weights</h3>
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
        <p>
          Facility Loose widens geo radius for spatial proximity candidates. Sensor Temporal raises date
          tolerance for re-analysis updates. Prior keep-separate decisions from earlier runs stay in the
          local decline ledger.
        </p>
        {#if declineLedger.length}
          <div class="ledger-chip">{declineLedger.length} prior keep-separate on file</div>
        {/if}
        <button class="cta pulse-cta" onclick={compare} disabled={loading}>
          {loading ? 'Running…' : 'Run comparison'}
        </button>
        <button class="ghost-link" onclick={() => (step = 'ingest')}>← Back to Ingest</button>
      </aside>
    </section>
  {/if}

  {#if step === 'results' && result}
    <section class="results">
      <div class="ops-banner rise">
        <div>
          <strong>Review queue</strong>
          <span class="mono">{pendingCount} pending · {decidedCount} decided · {keepSeparateCount} keep separate</span>
        </div>
        <button class="primary" onclick={goMerge}>
          Proceed to Merge board
        </button>
      </div>

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

      <div class="inventory-panel rise">
        <div class="inv-head">
          <h3>Category inventory</h3>
          <span class="muted">Compare source counts vs working merge — inflation may mean unresolved duplicates</span>
        </div>
        {#if inventory.alerts.length}
          <div class="inv-alerts">
            {#each inventory.alerts as a}
              <span class="flag {a.flag}">{a.category}: {flagLabel(a.flag)} (working {a.working} / max source {a.ceiling})</span>
            {/each}
          </div>
        {/if}
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Source A</th>
              <th>Source B</th>
              <th>Working merge</th>
              <th>Projected if auto-merge</th>
              <th>Signal</th>
            </tr>
          </thead>
          <tbody>
            {#each inventory.rows as r}
              <tr class:warn={!!r.flag}>
                <td>{r.category}</td>
                <td class="mono">{r.list_a}</td>
                <td class="mono">{r.list_b}</td>
                <td class="mono">{r.working}</td>
                <td class="mono">{r.projected}</td>
                <td>{r.flag ? flagLabel(r.flag) : '—'}</td>
              </tr>
            {/each}
            <tr class="totals">
              <td>Total</td>
              <td class="mono">{inventory.totals.list_a}</td>
              <td class="mono">{inventory.totals.list_b}</td>
              <td class="mono">{inventory.totals.working}</td>
              <td class="mono">{inventory.totals.projected}</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="toolbar">
        <input type="search" placeholder="Search names…" bind:value={search} />
        <div class="chips">
          {#each ['exact_match', 'strong_fuzzy_match', 'temporal_variant', 'spatial_proximity_candidate', 'weak_candidate', 'marked_distinct'] as c}
            <button class:on={filterClasses.includes(c)} onclick={() => toggleClass(c)}>
              <span class="dot" style="background:{CLASS_COLORS[c]}"></span>
              {CLASS_LABELS[c]}
            </button>
          {/each}
        </div>
        <div class="toolbar-actions">
          <button onclick={compare} disabled={loading}>Re-run</button>
          <button onclick={exportPackage}>Export package</button>
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
                <th>Hist</th>
              </tr>
            </thead>
            <tbody>
              {#each filteredMatches as m}
                <tr class:selected={selectedId === m.pair_id} class:prior={!!m.priorDecline} onclick={() => (selectedId = m.pair_id)}>
                  <td><span class="badge badge-{m.classification}">{CLASS_LABELS[m.classification] || m.classification}</span></td>
                  <td class="mono">{(m.scores.composite_score * 100).toFixed(0)}</td>
                  <td class="mono">{m.scores.geo_distance_m?.toFixed?.(0) ?? '—'}</td>
                  <td class="mono">{m.scores.name_similarity_pct?.toFixed?.(0) ?? '—'}%</td>
                  <td class="mono">{m.scores.date_diff_days?.toFixed?.(0) ?? '—'}</td>
                  <td>{m.entity_a.name}</td>
                  <td>{m.entity_b.name}</td>
                  <td class="mono">{m.priorDecline ? 'declined' : '—'}</td>
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
              priorDecline={selectedPrior}
              oncommit={commitDisposition}
              onclose={() => (selectedId = null)}
            />
          </div>
        {/if}
      </div>
    </section>
  {/if}

  {#if step === 'merge'}
    <section class="merge rise">
      <div class="merge-head">
        <div>
          <h2>Merge board</h2>
          <p class="muted">
            Commit dispositions on candidates in Results, then publish the working set for downstream systems.
          </p>
        </div>
        <div class="toolbar-actions">
          <button class="primary" onclick={publishWorkingSet} disabled={!workingSet.length && !keepSeparateCount}>
            Publish working set
          </button>
          <button onclick={exportWorkingCsv} disabled={!workingSet.length}>Download merge CSV</button>
          <button onclick={exportPackage}>Full package</button>
          <button onclick={() => (step = 'results')}>← Results</button>
        </div>
      </div>

      {#if published}
        <div class="publish-ok" role="status">{publishNote}</div>
      {/if}

      <div class="merge-grid">
        <div class="merge-card">
          <h3>Session metrics</h3>
          <dl class="metrics">
            <div><dt>Candidates</dt><dd class="mono">{result?.matches?.length ?? 0}</dd></div>
            <div><dt>Pending review</dt><dd class="mono">{pendingCount}</dd></div>
            <div><dt>Merged into working set</dt><dd class="mono">{workingSet.length}</dd></div>
            <div><dt>Keep separate (this run)</dt><dd class="mono">{keepSeparateCount}</dd></div>
            <div><dt>Prior declines on file</dt><dd class="mono">{declineLedger.length}</dd></div>
          </dl>
        </div>

        <div class="merge-card">
          <h3>Decline trend by category</h3>
          {#if !declineTrend.length}
            <p class="muted">No keep-separate history yet. Declines persist locally for future comparisons.</p>
          {:else}
            <table>
              <thead><tr><th>Category</th><th>Keep-separate count</th></tr></thead>
              <tbody>
                {#each declineTrend as t}
                  <tr><td>{t.category}</td><td class="mono">{t.count}</td></tr>
                {/each}
              </tbody>
            </table>
          {/if}
        </div>
      </div>

      <div class="inventory-panel">
        <div class="inv-head">
          <h3>Category breakout</h3>
          <span class="muted">If you expect 5 trucks but the working set shows 8, unresolved duplicates remain</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Source A</th>
              <th>Source B</th>
              <th>Working merge</th>
              <th>Projected</th>
              <th>Signal</th>
            </tr>
          </thead>
          <tbody>
            {#each inventory.rows as r}
              <tr class:warn={!!r.flag}>
                <td>{r.category}</td>
                <td class="mono">{r.list_a}</td>
                <td class="mono">{r.list_b}</td>
                <td class="mono">{r.working}</td>
                <td class="mono">{r.projected}</td>
                <td>{r.flag ? flagLabel(r.flag) : '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>

      <h3 class="subhead">Working merge set</h3>
      {#if !workingSet.length}
        <p class="muted">No merges committed yet. Open a candidate in Results, set disposition, and Commit.</p>
      {:else}
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Category</th>
              <th>Disposition</th>
              <th>Score</th>
              <th>Notes</th>
              <th>Committed</th>
            </tr>
          </thead>
          <tbody>
            {#each workingSet as row}
              <tr>
                <td>{row.name}</td>
                <td>{row.category}</td>
                <td><span class="badge badge-{row._match_classification}">{CLASS_LABELS[row._match_classification]}</span></td>
                <td class="mono">{(row._composite_score * 100).toFixed(0)}%</td>
                <td>{row._notes || '—'}</td>
                <td class="mono">{row._decided_at}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}

      <h3 class="subhead">Keep-separate (this run)</h3>
      {#if !keepSeparateCount}
        <p class="muted">No declines committed in this session.</p>
      {:else}
        <table>
          <thead>
            <tr><th>Pair</th><th>Action</th><th>Notes</th><th>At</th></tr>
          </thead>
          <tbody>
            {#each Object.entries(decisions).filter(([, d]) => d.action === 'keep_separate') as [pid, d]}
              <tr>
                <td class="mono">{pid}</td>
                <td><span class="badge badge-marked_distinct">Keep separate</span></td>
                <td>{d.notes || '—'}</td>
                <td class="mono">{d.at}</td>
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
    margin-bottom: 0.75rem;
    border-bottom: 1px solid var(--line);
    padding-bottom: 1rem;
  }
  .persist-banner {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 1rem;
    padding: 0.55rem 0.75rem;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: rgba(16, 40, 51, 0.9);
    font-size: 0.8rem;
    color: var(--paper-dim);
  }
  .persist-banner strong {
    color: var(--amber);
  }
  .persist-actions {
    display: flex;
    gap: 0.35rem;
  }
  .persist-actions button {
    background: transparent;
    border: 1px solid var(--line);
    color: var(--paper-dim);
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    font-size: 0.72rem;
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
  }
  .brand p {
    margin: 0.15rem 0 0;
    font-size: 0.85rem;
    color: var(--paper-dim);
  }
  .steps {
    display: flex;
    gap: 0.4rem;
  }
  .step {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    background: transparent;
    border: 1px solid var(--line);
    color: var(--gray);
    padding: 0.35rem 0.75rem;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 600;
  }
  .step-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--line);
  }
  .step.pending {
    opacity: 0.55;
  }
  .step.active {
    border-color: #5b8def;
    color: #9cbcf0;
    background: rgba(91, 141, 239, 0.12);
  }
  .step.active .step-dot {
    background: #5b8def;
    box-shadow: 0 0 0 3px rgba(91, 141, 239, 0.25);
  }
  .step.complete {
    border-color: var(--green);
    color: #7ddecf;
    background: rgba(42, 157, 143, 0.16);
  }
  .step.complete .step-dot {
    background: var(--green);
  }
  .step:disabled {
    cursor: not-allowed;
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
    max-width: 42rem;
    margin-bottom: 1.5rem;
  }
  h2 {
    margin: 0 0 0.5rem;
    font-size: 1.35rem;
  }
  h3 {
    margin: 0;
    font-size: 0.85rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--teal);
  }
  .subhead {
    margin: 1.25rem 0 0.5rem;
  }
  .hero-copy p,
  .muted {
    color: var(--paper-dim);
    line-height: 1.45;
    font-size: 0.9rem;
  }
  .cta {
    margin-top: 1rem;
    background: var(--teal);
    color: var(--ink);
    border: none;
    font-weight: 700;
    padding: 0.7rem 1.2rem;
    border-radius: 4px;
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
  .verify-bar {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 1rem;
    align-items: center;
    margin-top: 1rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--line);
    border-left: 3px solid var(--teal);
    border-radius: 4px;
    background: rgba(16, 40, 51, 0.85);
  }
  .verify-bar p {
    margin: 0.2rem 0 0;
  }
  .primary {
    background: var(--teal);
    color: var(--ink);
    border: none;
    font-weight: 650;
    padding: 0.55rem 0.9rem;
    border-radius: 4px;
  }
  .primary:disabled {
    opacity: 0.45;
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
  .config-side,
  .merge-card,
  .inventory-panel,
  .merge {
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
    border-radius: 4px;
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
  .ledger-chip {
    display: inline-block;
    margin: 0.6rem 0;
    padding: 0.25rem 0.55rem;
    border: 1px solid rgba(196, 69, 54, 0.4);
    color: #f0b4ad;
    border-radius: 3px;
    font-size: 0.72rem;
    font-family: var(--font-mono);
  }
  .ghost-link {
    display: inline-block;
    margin-top: 0.8rem;
    background: none;
    border: none;
    color: var(--gray);
    padding: 0;
  }
  .ops-banner {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.75rem;
    align-items: center;
    margin-bottom: 0.85rem;
    padding: 0.75rem 0.9rem;
    border: 1px solid var(--line);
    border-left: 3px solid var(--teal);
    border-radius: 4px;
    background: rgba(16, 40, 51, 0.85);
  }
  .ops-banner strong {
    display: block;
    margin-bottom: 0.15rem;
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
  .inventory-panel {
    margin-bottom: 0.85rem;
  }
  .inv-head {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 0.5rem;
    align-items: baseline;
  }
  .inv-alerts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.55rem;
  }
  .flag {
    font-size: 0.72rem;
    font-family: var(--font-mono);
    padding: 0.2rem 0.45rem;
    border-radius: 3px;
  }
  .flag.inflation {
    background: rgba(196, 69, 54, 0.15);
    color: #f0b4ad;
    border: 1px solid rgba(196, 69, 54, 0.35);
  }
  .flag.deflation,
  .flag.watch {
    background: rgba(244, 162, 97, 0.12);
    color: #f6c08a;
    border: 1px solid rgba(244, 162, 97, 0.35);
  }
  tr.warn td {
    color: #f6c08a;
  }
  tr.totals td {
    font-weight: 600;
    border-top: 1px solid var(--line);
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
    border-radius: 4px;
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
    flex-wrap: wrap;
    gap: 0.35rem;
  }
  .toolbar-actions button:not(.primary) {
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
  .table-wrap tr.prior td:last-child {
    color: #f0b4ad;
  }
  .map-pane {
    min-height: 100%;
  }
  .merge-head {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .merge-head p {
    margin: 0.25rem 0 0;
  }
  .publish-ok {
    background: rgba(42, 157, 143, 0.15);
    border: 1px solid rgba(42, 157, 143, 0.4);
    color: #7ddecf;
    padding: 0.55rem 0.75rem;
    border-radius: 4px;
    margin-bottom: 0.85rem;
    font-size: 0.85rem;
  }
  .merge-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.85rem;
    margin-bottom: 0.85rem;
  }
  @media (max-width: 800px) {
    .merge-grid {
      grid-template-columns: 1fr;
    }
  }
  .metrics {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 0.35rem 1rem;
    margin: 0.75rem 0 0;
  }
  .metrics > div {
    display: contents;
  }
  .metrics dt {
    color: var(--gray);
    font-size: 0.8rem;
  }
  .metrics dd {
    margin: 0;
    text-align: right;
    font-size: 0.9rem;
  }
</style>
