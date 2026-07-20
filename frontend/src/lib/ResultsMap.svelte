<script>
  import { onDestroy, onMount } from 'svelte'
  import L from 'leaflet'
  import { CLASS_COLORS } from '../lib/api.js'

  let {
    matches = [],
    unmatchedA = [],
    unmatchedB = [],
    selectedId = null,
    activeClasses = [],
    onselect = () => {},
  } = $props()

  let mapEl
  let map
  let layerGroup
  let markersById = new Map()

  onMount(() => {
    map = L.map(mapEl, { zoomControl: true, attributionControl: true }).setView([28.39, -80.61], 10)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap &copy; CARTO',
      maxZoom: 19,
    }).addTo(map)
    layerGroup = L.layerGroup().addTo(map)
    redraw()
    setTimeout(() => map.invalidateSize(), 80)
  })

  onDestroy(() => {
    if (map) map.remove()
  })

  function circleIcon(color, selected) {
    const size = selected ? 16 : 12
    return L.divIcon({
      className: '',
      html: `<span style="display:block;width:${size}px;height:${size}px;border-radius:50%;background:${color};border:2px solid #e8f1f2;box-shadow:0 0 0 ${selected ? 3 : 0}px rgba(46,196,182,0.45)"></span>`,
      iconSize: [size, size],
      iconAnchor: [size / 2, size / 2],
    })
  }

  function redraw() {
    if (!map || !layerGroup) return
    layerGroup.clearLayers()
    markersById = new Map()
    const bounds = []

    const visible = matches.filter((m) => activeClasses.length === 0 || activeClasses.includes(m.classification))
    for (const m of visible) {
      const color = CLASS_COLORS[m.classification] || '#7a93a0'
      const a = m.entity_a
      const b = m.entity_b
      if (a.lat != null && a.lon != null && b.lat != null && b.lon != null) {
        const line = L.polyline(
          [
            [a.lat, a.lon],
            [b.lat, b.lon],
          ],
          { color, weight: selectedId === m.pair_id ? 3 : 1.5, opacity: 0.75, dashArray: m.classification.includes('spatial') ? '4 4' : undefined },
        )
        line.addTo(layerGroup)
        line.on('click', () => onselect(m.pair_id))
      }
      for (const [ent, label] of [
        [a, 'A'],
        [b, 'B'],
      ]) {
        if (ent.lat == null || ent.lon == null) continue
        const mk = L.marker([ent.lat, ent.lon], {
          icon: circleIcon(color, selectedId === m.pair_id),
        })
        mk.bindPopup(
          `<strong>${ent.name || '(unnamed)'}</strong><br/><span style="font-family:monospace;font-size:11px">${m.classification}</span><br/>List ${label} · composite ${(m.scores.composite_score * 100).toFixed(0)}%`,
        )
        mk.on('click', () => onselect(m.pair_id))
        mk.addTo(layerGroup)
        markersById.set(`${m.pair_id}-${label}`, mk)
        bounds.push([ent.lat, ent.lon])
      }
    }

    // Unmatched layers (muted)
    if (activeClasses.length === 0 || activeClasses.includes('unmatched')) {
      for (const ent of unmatchedA) {
        if (ent.lat == null) continue
        L.circleMarker([ent.lat, ent.lon], { radius: 4, color: '#c44536', fillOpacity: 0.35, weight: 1 })
          .bindPopup(`A unmatched: ${ent.name}`)
          .addTo(layerGroup)
        bounds.push([ent.lat, ent.lon])
      }
      for (const ent of unmatchedB) {
        if (ent.lat == null) continue
        L.circleMarker([ent.lat, ent.lon], { radius: 4, color: '#5b8def', fillOpacity: 0.35, weight: 1 })
          .bindPopup(`B unmatched: ${ent.name}`)
          .addTo(layerGroup)
        bounds.push([ent.lat, ent.lon])
      }
    }

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [28, 28], maxZoom: 13 })
    }
    setTimeout(() => map.invalidateSize(), 50)
  }

  $effect(() => {
    matches
    unmatchedA
    unmatchedB
    activeClasses
    selectedId
    redraw()
  })
</script>

<div class="map-wrap" bind:this={mapEl}></div>

<style>
  .map-wrap {
    width: 100%;
    height: 100%;
    min-height: 320px;
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid var(--line);
  }
</style>
