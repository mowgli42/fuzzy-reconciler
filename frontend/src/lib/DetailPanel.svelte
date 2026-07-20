<script>
  import { CLASS_LABELS } from './api.js'

  let {
    pair = null,
    priorDecline = null,
    oncommit = () => {},
    onclose = () => {},
  } = $props()

  let notes = $state('')
  /** 0 = merge, 1 = temporal update, 2 = keep separate */
  let disposition = $state(0)

  $effect(() => {
    if (!pair) return
    notes = pair.notes || ''
    if (pair.classification === 'marked_distinct' || priorDecline) disposition = 2
    else if (
      pair.classification === 'temporal_variant' ||
      pair.classification === 'confirmed_temporal'
    )
      disposition = 1
    else if (
      pair.classification === 'confirmed_match' ||
      pair.classification === 'exact_match' ||
      pair.classification === 'strong_fuzzy_match'
    )
      disposition = 0
    else disposition = 0
  })

  let bars = $derived(
    pair
      ? [
          { label: 'Geo', value: pair.scores.geo_score, color: '#2ec4b6' },
          { label: 'Name', value: pair.scores.name_score, color: '#5b8def' },
          { label: 'Attrs', value: pair.scores.attr_score, color: '#f4a261' },
          { label: 'Temporal', value: pair.scores.temporal_score, color: '#e76f51' },
        ]
      : [],
  )

  const dispositionMeta = [
    { value: 0, label: 'Merge', hint: 'Accept as one entity in the working set' },
    { value: 1, label: 'Temporal update', hint: 'Same entity; prefer newer analysis date' },
    { value: 2, label: 'Keep separate', hint: 'Decline merge — retain both records' },
  ]

  function actionForDisposition(d) {
    const n = Number(d)
    if (n === 1) return 'confirm_temporal'
    if (n === 2) return 'keep_separate'
    return 'confirm_match'
  }

  function fields(ent) {
    if (!ent) return []
    const base = [
      ['id', ent.id],
      ['name', ent.name],
      ['lat', ent.lat],
      ['lon', ent.lon],
      ['analyzed_at', ent.analyzed_at],
      ['category', ent.category],
    ]
    const attrs = Object.entries(ent.attributes || {}).map(([k, v]) => [`attr.${k}`, v])
    return [...base, ...attrs]
  }

  function commit() {
    oncommit(pair.pair_id, actionForDisposition(disposition), notes)
  }
</script>

{#if pair}
  <aside class="panel rise">
    <header>
      <div>
        <div class="eyebrow">Candidate {pair.pair_id}</div>
        <div class="title-row">
          <span class="badge badge-{pair.classification}">{CLASS_LABELS[pair.classification] || pair.classification}</span>
          <span class="score">{(pair.scores.composite_score * 100).toFixed(0)}%</span>
        </div>
      </div>
      <button class="ghost" onclick={onclose} aria-label="Close">✕</button>
    </header>

    {#if priorDecline}
      <div class="prior" role="status">
        <strong>Prior keep-separate</strong>
        Declined {new Date(priorDecline.declined_at).toLocaleString()}
        {#if priorDecline.notes}
          — {priorDecline.notes}
        {/if}
      </div>
    {/if}

    <div class="meta">
      {#if pair.scores.geo_distance_m != null}
        <span>{pair.scores.geo_distance_m.toFixed(0)} m apart</span>
      {/if}
      {#if pair.scores.date_diff_days != null}
        <span>{pair.scores.date_diff_days.toFixed(0)} day date Δ</span>
      {/if}
      {#if pair.scores.name_similarity_pct != null}
        <span>{pair.scores.name_similarity_pct.toFixed(0)}% name</span>
      {/if}
    </div>

    <section class="bars">
      {#each bars as b}
        <div class="bar-row">
          <span>{b.label}</span>
          <div class="track"><div class="fill" style="width: {b.value * 100}%; background: {b.color}"></div></div>
          <span class="mono">{(b.value * 100).toFixed(0)}</span>
        </div>
      {/each}
    </section>

    <section class="compare">
      <div>
        <h3>Source A</h3>
        {#each fields(pair.entity_a) as [k, v]}
          <div class="field" class:diff={String(v) !== String(fields(pair.entity_b).find((x) => x[0] === k)?.[1] ?? '')}>
            <span class="k">{k}</span>
            <span class="v">{v ?? '—'}</span>
          </div>
        {/each}
      </div>
      <div>
        <h3>Source B</h3>
        {#each fields(pair.entity_b) as [k, v]}
          <div class="field" class:diff={String(v) !== String(fields(pair.entity_a).find((x) => x[0] === k)?.[1] ?? '')}>
            <span class="k">{k}</span>
            <span class="v">{v ?? '—'}</span>
          </div>
        {/each}
      </div>
    </section>

    <section class="disposition">
      <div class="disp-head">
        <span>Disposition</span>
        <strong>{dispositionMeta[Number(disposition)].label}</strong>
      </div>
      <input
        type="range"
        min="0"
        max="2"
        step="1"
        bind:value={disposition}
        aria-label="Disposition: merge, temporal update, or keep separate"
      />
      <div class="disp-labels">
        {#each dispositionMeta as d}
          <button type="button" class:on={Number(disposition) === d.value} onclick={() => (disposition = d.value)}>
            {d.label}
          </button>
        {/each}
      </div>
      <p class="hint">{dispositionMeta[Number(disposition)].hint}</p>
    </section>

    <label class="notes">
      Operator notes
      <textarea bind:value={notes} rows="2" placeholder="Rationale stored with the decision ledger…"></textarea>
    </label>

    <div class="actions">
      <button class="primary" class:decline={Number(disposition) === 2} onclick={commit}>
        {Number(disposition) === 2 ? 'Commit keep separate' : 'Commit disposition'}
      </button>
    </div>
  </aside>
{/if}

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    background: linear-gradient(180deg, var(--panel-2), var(--panel));
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 1rem;
    max-height: 100%;
    overflow: auto;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .eyebrow {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--gray);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .title-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin-top: 0.25rem;
  }
  .score {
    font-family: var(--font-mono);
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--teal);
  }
  .ghost {
    background: transparent;
    border: none;
    color: var(--paper-dim);
    font-size: 1rem;
  }
  .prior {
    background: rgba(196, 69, 54, 0.12);
    border: 1px solid rgba(196, 69, 54, 0.4);
    border-radius: 4px;
    padding: 0.55rem 0.65rem;
    font-size: 0.78rem;
    color: #f0b4ad;
    line-height: 1.35;
  }
  .prior strong {
    display: block;
    margin-bottom: 0.15rem;
    color: #f6c4be;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-size: 0.68rem;
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--paper-dim);
  }
  .meta span {
    border: 1px solid var(--line);
    padding: 0.15rem 0.45rem;
    border-radius: 3px;
  }
  .bars {
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }
  .bar-row {
    display: grid;
    grid-template-columns: 4.5rem 1fr 2rem;
    gap: 0.4rem;
    align-items: center;
    font-size: 0.78rem;
  }
  .track {
    height: 8px;
    background: rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    overflow: hidden;
  }
  .fill {
    height: 100%;
    transition: width 0.4s ease;
  }
  .mono {
    font-family: var(--font-mono);
    text-align: right;
  }
  .compare {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  h3 {
    margin: 0 0 0.4rem;
    font-size: 0.75rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--teal);
  }
  .field {
    display: grid;
    grid-template-columns: 5.5rem 1fr;
    gap: 0.3rem;
    font-size: 0.72rem;
    padding: 0.15rem 0;
    border-bottom: 1px solid rgba(42, 74, 87, 0.5);
  }
  .field.diff .v {
    color: var(--amber);
  }
  .k {
    font-family: var(--font-mono);
    color: var(--gray);
  }
  .v {
    word-break: break-word;
  }
  .disposition {
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 0.7rem;
    background: rgba(0, 0, 0, 0.18);
  }
  .disp-head {
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
    margin-bottom: 0.45rem;
    color: var(--paper-dim);
  }
  .disp-head strong {
    color: var(--paper);
  }
  .disposition input[type='range'] {
    width: 100%;
    accent-color: var(--amber);
  }
  .disp-labels {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 0.25rem;
    margin-top: 0.4rem;
  }
  .disp-labels button {
    background: transparent;
    border: 1px solid var(--line);
    color: var(--gray);
    border-radius: 3px;
    padding: 0.25rem 0.2rem;
    font-size: 0.68rem;
  }
  .disp-labels button.on {
    border-color: var(--teal);
    color: var(--teal);
    background: rgba(46, 196, 182, 0.08);
  }
  .hint {
    margin: 0.45rem 0 0;
    font-size: 0.72rem;
    color: var(--gray);
    line-height: 1.35;
  }
  .notes {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.8rem;
    color: var(--paper-dim);
  }
  textarea {
    background: rgba(0, 0, 0, 0.25);
    border: 1px solid var(--line);
    border-radius: 4px;
    color: var(--paper);
    padding: 0.5rem;
    resize: vertical;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }
  .primary {
    border-radius: 4px;
    padding: 0.55rem 0.85rem;
    font-size: 0.85rem;
    font-weight: 700;
    border: 1px solid transparent;
    background: var(--teal);
    color: var(--ink);
    width: 100%;
  }
  .primary.decline {
    background: transparent;
    border-color: var(--danger);
    color: #f0b4ad;
  }
</style>
