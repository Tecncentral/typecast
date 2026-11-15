/* Visible business summary for the Director's Room: what the drive limit did, the scouting
   scenario, and a real location against a standing set or a built set. Pure helpers are
   exported for Node tests; DOM wiring runs only in a browser. Nothing here is a measured saving. */
(function (root) {
  'use strict';

  /* What the road-time limit did to the retrieved pool. Counts properties, not frames. */
  function driveSummary(response, assignments) {
    if (!response || !Array.isArray(response.scenes)) return null;
    const limit = typeof response.commute_limit_minutes === 'number' ? response.commute_limit_minutes : null;
    const byProperty = new Map(), byShot = new Map();
    for (const scene of response.scenes) for (const c of scene.candidates || []) {
      const pid = c?.shot?.property_id;
      if (!pid) continue;
      if (!byProperty.has(pid)) byProperty.set(pid, c.commute || null);
      byShot.set(`${scene.id}|${c.shot.shot_id}`, c);
    }
    const routed = c => c && c.status === 'estimated' && typeof c.minutes === 'number' && Number.isFinite(c.minutes) && c.minutes >= 0;
    let within = 0, tooFar = 0, unknown = 0;
    for (const commute of byProperty.values()) {
      if (!routed(commute)) unknown++;
      else if (limit !== null && commute.minutes > limit) tooFar++;
      else within++;
    }
    const selected = (assignments || []).map(a => {
      const commute = byShot.get(`${a.scene_id}|${a.shot_id}`)?.commute || byProperty.get(a.property_id) || null;
      const heading = response.scenes.find(s => s.id === a.scene_id)?.heading || a.scene_id;
      return { sceneId: a.scene_id, heading, propertyId: a.property_id,
        minutes: routed(commute) ? commute.minutes : null,
        miles: routed(commute) && typeof commute.miles === 'number' && Number.isFinite(commute.miles) ? commute.miles : null };
    });
    const known = selected.map(x => x.minutes).filter(m => m !== null);
    return { limit, total: byProperty.size, within: limit === null ? null : within, tooFar: limit === null ? null : tooFar,
      unknown, routed: within + tooFar, selected,
      slowestSelected: known.length && known.length === selected.length ? Math.max(...known) : null, mock: response.mode === 'mock' };
  }

  function driveText(d) {
    if (!d) return { headline: 'Set a base', sub: 'Pick a home or production base and a maximum drive, then Build plan.' };
    if (d.limit === null) return { headline: 'Filter off',
      sub: `${d.total} retrieved propert${d.total === 1 ? 'y' : 'ies'} considered with no drive limit. Tick “Only locations within this drive time” to filter by road time.` };
    const parts = [];
    if (d.tooFar) parts.push(`${d.tooFar} too far`);
    if (d.unknown) parts.push(`${d.unknown} with no known route`);
    const excluded = d.tooFar + d.unknown;
    return { headline: `${d.within} of ${d.total} within ${d.limit} min`,
      sub: `${excluded ? `${excluded} excluded (${parts.join(', ')}).` : 'None excluded.'} One-way road time from your pin, OSRM / OpenStreetMap, no live traffic.${d.mock ? ' MOCK fixtures: routing is not called.' : ''}` };
  }

  function scoutText(ctx, money) {
    const r = ctx?.result, a = ctx?.assumptions;
    if (!r || r.error) return { headline: '—', sub: r?.error || 'Build a complete plan to see the scenario.' };
    const daily = a?.billing === 'daily';
    const qty = daily ? r.scoutDaysReleased : r.scoutHoursReleased, unit = daily ? 'scout day' : 'scout hour';
    const basis = daily ? `${money(a.dailyRate)} per day` : `${money(a.scoutRate)} per hour`;
    const value = r.laborCapacityValue;
    const cash = r.cashPotential == null ? 'Cash impact unconfirmed until the producer says which days can be cancelled.'
      : `${money(Math.abs(r.cashPotential))} ${r.cashPotential >= 0 ? 'potential cash avoided' : 'additional cash cost'}.`;
    return { headline: `${value < 0 ? '−' : ''}${money(Math.abs(value))}`,
      sub: `${value < 0 ? 'Added' : 'Released'} labor value: ${qty == null ? 'hours unknown' : `${Math.abs(qty)} ${unit}${Math.abs(qty) === 1 ? '' : 's'}`} at ${basis}. SCENARIO from your inputs, not a measured saving. ${cash}` };
  }

  /* The tile reads the shared cost model (data/cost_model.cost_compare via /api/shortlist/costs), the same
     numbers as the shortlist's Travel and budget panel: likely totals with low-high ranges, whole dollars. */
  const usd = n => `$${Math.round(n).toLocaleString('en-US')}`;
  function setText(c) {
    if (!c || c.error) return { headline: '—', sub: c?.error || 'Build a plan to price its location.' };
    const found = c.picks?.[0]?.found_location, alt = c.alternatives || {};
    if (!found || !alt.build_set) return { headline: '—', sub: 'No cost estimate for this location.' };
    const diff = alt.build_set.total_usd - found.total_usd;
    const headline = diff > 0 ? `${usd(diff)} less` : diff < 0 ? `${usd(-diff)} more` : 'Same cost';
    const days = `${c.shoot_days} shoot day${c.shoot_days === 1 ? '' : 's'}`;
    const range = o => `${usd(o.total_usd)} (${usd(o.total_low_usd)}–${usd(o.total_high_usd)})`;
    return { headline, sub: `than building a set (likely figures), for ${days} at ${Math.round(c.scene_sqft).toLocaleString('en-US')} sq ft. ` +
      `Real location ${range(found)} · standing set ${range(alt.standing_set)} · build ${range(alt.build_set)}` +
      (alt.cgi ? ` · CGI ${range(alt.cgi)}` : '') + '.' };
  }

  /* One row per selected property, with how many scenes shoot there. */
  function selectedLocations(d) {
    const rows = new Map();
    for (const x of d?.selected || []) {
      const row = rows.get(x.propertyId) || { propertyId: x.propertyId, scenes: 0, minutes: x.minutes, miles: x.miles };
      row.scenes++; rows.set(x.propertyId, row);
    }
    return [...rows.values()];
  }

  const api = { driveSummary, driveText, scoutText, setText, selectedLocations };
  if (typeof module === 'object' && module.exports) { module.exports = api; return; }
  root.TypecastImpactText = api;
  if (typeof document === 'undefined') return;

  const $ = id => document.getElementById(id);
  const lvs = root.TypecastLocationVsSet;
  // [key, label, step, default, min, max]: the same inputs and limits as the shortlist's budget panel.
  const FIELDS = [
    ['sceneSqft', 'Scene size (sq ft)', 100, 2000, 100, 1000000],
    ['shootDays', 'Shoot days at this location', 1, 2, 1, 60],
  ];
  let last = null, lease = { pid: null, data: null }, leaseSeq = 0, costSeq = 0, costTimer = null;

  function inputs() {
    const out = {};
    for (const [key, , , , min, max] of FIELDS) {
      const raw = $('lvs_' + key).value.trim(), n = Number(raw);
      out[key] = raw !== '' && Number.isFinite(n) && n >= min && n <= max && (key !== 'shootDays' || Number.isInteger(n)) ? n : null;
    }
    return out;
  }
  const set = (id, text) => { const el = $(id); if (el) el.textContent = text; };

  function selectedProperty(s) {
    const a = (s?.assignments || []).find(x => x.scene_id === s.selectedScene) || (s?.assignments || [])[0];
    if (!a) return null;
    const candidate = s.response?.scenes?.find(sc => sc.id === a.scene_id)?.candidates?.find(c => c.shot?.shot_id === a.shot_id);
    return { id: a.property_id, property: candidate?.property || null };
  }

  function renderLease(s) {
    const chosen = s ? selectedProperty(s) : null, note = $('lvsLease');
    if (!note) return;
    if (!chosen) { note.textContent = ''; return; }
    const p = chosen.property, facts = p ? [p.type, typeof p.size_sqft === 'number' ? `${Math.round(p.size_sqft).toLocaleString('en-US')} sq ft` : null].filter(Boolean).join(', ') : '';
    const head = `Selected property ${chosen.id}${facts ? ` (CoStar: ${facts})` : ''}. `;
    const d = lease.pid === chosen.id ? lease.data : null;
    if (!d) { note.textContent = head + (s.response?.mode === 'mock' ? 'Mock fixtures carry no lease evidence.' : 'Checking CoStar lease evidence…'); return; }
    note.textContent = head + (d.status === 'kit' && typeof d.usd_per_sf_year === 'number'
      ? `CoStar lease evidence (tier ${d.tier}${d.date ? `, ${d.date}` : ''}): ${lvs.money(d.usd_per_sf_year)} per sq ft per year${typeof d.daily_floor_usd === 'number' ? `, a prorated floor of ${lvs.money(d.daily_floor_usd)} per day` : ''}. Reference only: not a filming fee or permission, and not added to the totals.`
      : `Lease evidence unknown: ${d.reason || 'no record'}`);
  }

  async function loadLease(s) {
    const chosen = s ? selectedProperty(s) : null;
    if (!chosen || s.response?.mode !== 'live' || lease.pid === chosen.id) return;
    const seq = ++leaseSeq; lease = { pid: chosen.id, data: null };
    try {
      const response = await fetch(`/api/production/lease/${encodeURIComponent(chosen.id)}`);
      const data = response.ok ? await response.json() : { status: 'unknown', reason: `Lease lookup failed (${response.status}).` };
      if (seq !== leaseSeq) return;
      lease = { pid: chosen.id, data };
    } catch { if (seq === leaseSeq) lease = { pid: chosen.id, data: { status: 'unknown', reason: 'Lease lookup unavailable.' } }; }
    renderSet(); renderLease(root.typecastPlanningSnapshot?.());
  }

  function paintSet(c) {
    const text = setText(c), box = $('lvsResult');
    set('impactSet', text.headline); set('impactSetSub', text.sub);
    if (!box) return;
    box.replaceChildren();
    const line = (tag, t) => { const el = document.createElement(tag); el.textContent = t; box.append(el); return el; };
    if (!c || c.error || !c.picks?.[0]) return void line('p', text.sub);
    const options = [['Real location', c.picks[0].found_location], ['Standing set', c.alternatives.standing_set],
      ['Build a set on a stage', c.alternatives.build_set], ['CGI', c.alternatives.cgi]].filter(([, o]) => o);
    const cheapest = options.reduce((a, b) => (b[1].total_usd < a[1].total_usd ? b : a));
    line('h3', `${cheapest[0]} is the lowest likely cost for this scene.`);
    for (const [name, o] of options) {
      line('p', `${name}: ${usd(o.total_usd)} likely, ${usd(o.total_low_usd)}–${usd(o.total_high_usd)}. `
        + (o.lines || []).map(l => `${l.label} ${usd(l.amount_usd)} (${l.formula})`).join('; ') + '.');
    }
    const sources = $('lvsSources');
    if (sources) {
      sources.replaceChildren();
      for (const [name, s] of Object.entries(c.sources || {})) {
        const li = document.createElement('li');
        li.textContent = `${name.replace(/_/g, ' ')}: ${s.source} (${s.quality}).`;
        sources.append(li);
      }
    }
  }

  function renderSet() {
    if (!$('lvs_shootDays')) return;
    clearTimeout(costTimer);
    costTimer = setTimeout(loadSet, 250);
  }

  async function loadSet() {
    const s = root.typecastPlanningSnapshot?.(), chosen = s ? selectedProperty(s) : null, v = inputs();
    const seq = ++costSeq;
    if (!chosen) return void paintSet(null);
    if (v.sceneSqft === null || v.shootDays === null) return void paintSet({ error: 'Scene size must be 100–1,000,000 sq ft and shoot days a whole number from 1 to 60.' });
    const row = selectedLocations(s.response ? driveSummary(s.response, s.assignments) : null).find(x => x.propertyId === chosen.id);
    const minutes = typeof row?.minutes === 'number' && row.minutes <= 600 ? { [chosen.id]: row.minutes } : {};
    try {
      const response = await fetch('/api/shortlist/costs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ picks: [{ property_id: chosen.id }], scene_sqft: v.sceneSqft, shoot_days: v.shootDays, drive_minutes: minutes }) });
      const data = await response.json().catch(() => ({}));
      if (seq !== costSeq) return;
      paintSet(response.ok ? data : { error: `Cost estimate unavailable (${response.status}).` });
    } catch { if (seq === costSeq) paintSet({ error: 'Cost estimate unavailable.' }); }
  }

  function render(ctx) {
    last = ctx || last;
    const s = last?.snapshot, d = s?.response ? driveSummary(s.response, s.assignments) : null, text = driveText(d);
    set('impactDrive', text.headline); set('impactDriveSub', text.sub);
    $('impactDriveTile')?.classList.toggle('is-on', !!d && d.limit !== null);
    const list = $('impactDriveList');
    if (list) {
      list.replaceChildren();
      for (const x of selectedLocations(d)) {
        const li = document.createElement('li');
        li.textContent = `Property ${x.propertyId} (${x.scenes} scene${x.scenes === 1 ? '' : 's'}): ${x.minutes === null ? 'drive time unknown' : `${x.minutes.toFixed(0)} min${x.miles === null ? '' : `, ${x.miles.toFixed(1)} mi`} one way`}`;
        list.append(li);
      }
    }
    const scout = scoutText(last, lvs ? lvs.money : n => `$${n}`);
    set('impactScout', scout.headline); set('impactScoutSub', scout.sub);
    renderSet(); renderLease(s); loadLease(s);
  }
  root.TypecastImpact = { render };

  root.addEventListener('DOMContentLoaded', () => {
    if (!lvs || !$('lvsInputs')) return;
    for (const [key, title, step, value, min, max] of FIELDS) {
      const label = document.createElement('label'); label.textContent = title;
      const input = document.createElement('input');
      Object.assign(input, { id: 'lvs_' + key, type: 'number', min: String(min), max: String(max), step: String(step), value: String(value) });
      input.addEventListener('input', renderSet); label.append(input); $('lvsInputs').append(label);
    }
    // A drive limit a reviewer moves should visibly change the plan: rebuild when the slider is released or the filter toggled.
    const rebuild = () => {
      const s = root.typecastPlanningSnapshot?.(), build = $('build');
      if (!s?.response || !build || build.disabled) return;
      if ($('commuteOn').checked && root.TypecastPlanning?.validate?.()) return;
      build.click();
    };
    $('driveLimit')?.addEventListener('change', () => { if ($('commuteOn').checked) rebuild(); });
    $('commuteOn')?.addEventListener('change', rebuild);
    // Start from the sourced union day-rate example unless this browser has a stored budget case.
    let stored = null;
    try { stored = localStorage.getItem('typecast-producer-budget-v1'); } catch { /* storage unavailable: treat as none */ }
    if (!stored) $('commercialRatePreset')?.click();
    render({ snapshot: root.typecastPlanningSnapshot?.() });
  });
})(typeof globalThis !== 'undefined' ? globalThis : this);
