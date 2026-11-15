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

  function setText(r, lvs) {
    if (!r || r.error) return { headline: '—', sub: r?.error || '' };
    const m = lvs.money, bound = r.buildIsLowerBound ? '≥ ' : '';
    const headline = r.locationVsBuild > 0 ? `${bound}${m(r.locationVsBuild)} less` : r.locationVsBuild < 0 ? `${m(-r.locationVsBuild)} more` : 'Same cost';
    const days = `${r.assumptions.shootDays} shoot day${r.assumptions.shootDays === 1 ? '' : 's'}`;
    return { headline, sub: `than building a set, for ${days}. Real location ${m(r.location)} · standing set ${m(r.standing)} · build ${bound}${m(r.build)}. SCENARIO at published rates.` };
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
  const FIELDS = [
    ['shootDays', 'Shoot days at this location', 1], ['locationHourly', 'Real location: rental per hour ($)', 0.01, 'locationHourly'],
    ['locationHoursPerDay', 'Real location: hours per day', 0.5], ['locationPrepDays', 'Real location: paid prep days', 1],
    ['standingShootDay', 'Standing set: per shoot day ($)', 0.01, 'standingShootDay'], ['standingPrepDay', 'Standing set: per prep or strike day ($)', 0.01],
    ['standingPrepDays', 'Standing set: prep or strike days', 1], ['stageDay', 'Build: stage rental per day ($)', 0.01, 'stageDay'],
    ['buildDays', 'Build: construction days (your assumption)', 1], ['strikeDays', 'Build: strike days (your assumption)', 1],
    ['buildCrew', 'Build: construction crew (your assumption)', 1], ['crewHourly', 'Build: crew pay per hour ($)', 0.01, 'crewHourly'],
    ['crewHoursPerDay', 'Build: crew hours per day', 0.5], ['materials', 'Build: materials and dressing ($) — blank if unknown', 0.01],
  ];
  let last = null, lease = { pid: null, data: null }, leaseSeq = 0;

  function inputs() {
    const out = {};
    for (const [key] of FIELDS) {
      const raw = $('lvs_' + key).value.trim();
      out[key] = raw === '' ? (key === 'materials' ? null : NaN) : Number(raw);
    }
    if (lease.data && typeof lease.data.daily_floor_usd === 'number') out.leaseFloorPerDay = lease.data.daily_floor_usd;
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

  function renderSet() {
    if (!lvs || !$('lvs_shootDays')) return;
    const r = lvs.compare(inputs()), text = setText(r, lvs), box = $('lvsResult');
    set('impactSet', text.headline); set('impactSetSub', text.sub);
    box.replaceChildren();
    const line = (tag, t) => { const el = document.createElement(tag); el.textContent = t; box.append(el); };
    if (r.error) return void line('p', r.error);
    const m = lvs.money, a = r.assumptions;
    line('h3', lvs.verdict(r));
    line('p', `Real location: ${m(a.locationHourly)}/h × ${a.locationHoursPerDay} h × ${a.shootDays + a.locationPrepDays} day(s) = ${m(r.location)}.`);
    line('p', `Standing set: ${m(a.standingShootDay)} × ${a.shootDays} shoot day(s) + ${m(a.standingPrepDay)} × ${a.standingPrepDays} prep day(s) = ${m(r.standing)}.`);
    line('p', `Build a set: stage ${m(a.stageDay)} × ${r.parts.stageDays} days = ${m(r.parts.stage)}; crew ${a.buildCrew} × ${m(a.crewHourly)}/h × ${a.crewHoursPerDay} h × ${a.buildDays + a.strikeDays} days = ${m(r.parts.labor)}; materials ${r.parts.materials === null ? 'not entered' : m(r.parts.materials)}. Total ${r.buildIsLowerBound ? 'at least ' : ''}${m(r.build)}.`);
    line('p', r.breakEvenShootDays === null ? 'At these day rates the built set never becomes cheaper with more shoot days.'
      : `The built set would match the location at about ${r.breakEvenShootDays} shoot day(s).`);
    if (r.leaseFloorTotal !== null) line('p', `CoStar prorated lease floor for the same days: ${m(r.leaseFloorTotal)} (reference only).`);
    line('p', 'No crew, lighting, permits, insurance, travel or fringes in any column. Scenario only.');
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
    for (const [key, title, step, sourceKey] of FIELDS) {
      const label = document.createElement('label'); label.textContent = title;
      const input = document.createElement('input');
      Object.assign(input, { id: 'lvs_' + key, type: 'number', min: key === 'shootDays' ? '1' : '0', max: '100000000', step: String(step),
        value: lvs.DEFAULTS[key] == null ? '' : String(lvs.DEFAULTS[key]) });
      if (sourceKey) input.title = lvs.SOURCES[sourceKey].label;
      input.addEventListener('input', renderSet); label.append(input); $('lvsInputs').append(label);
    }
    for (const source of Object.values(lvs.SOURCES)) {
      const li = document.createElement('li'), link = document.createElement('a');
      link.href = source.url; link.target = '_blank'; link.rel = 'noopener'; link.textContent = source.label;
      li.append(link, ` (${source.kind}, checked ${source.checked})`); $('lvsSources').append(li);
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
