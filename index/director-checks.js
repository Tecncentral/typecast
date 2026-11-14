'use strict';
// Pure, deterministic checks for the Director's Room: scene-to-location fit evidence, scene continuity,
// and the on-site checklist. No DOM, no network, no model. Every statement is derived only from fields the
// plan response or the user's own text actually supplies; missing data stays "unknown", never "ok".
(function (root) {
  const KIND_LABEL = { conflict: 'Conflict', unknown: 'Unknown', estimate: 'Consistent (estimated)', match: 'Matches', similarity: 'Visual similarity', info: 'Note' };
  const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  const known = (s) => s === 'measured' || s === 'estimated';
  const M2_PER_SQFT = 0.09290304, M_PER_FT = 0.3048;

  // ---- numeric requirements the user wrote in the scene text (lower bounds only) ----
  const BOUND = '(at least|minimum of|minimum|min\\.?|no less than|over|more than)';
  const AREA_UNIT = '(m2|m²|sq\\.? ?m|sqm|square met(?:er|re)s?|sq\\.? ?ft|sqft|square feet|square foot)';
  const LEN_UNIT = '(m|meters?|metres?|ft|feet|foot)';
  function toM2(v, unit) { return /ft|feet|foot/i.test(unit) ? v * M2_PER_SQFT : v; }
  function toM(v, unit) { return /^(ft|feet|foot)$/i.test(unit) ? v * M_PER_FT : v; }
  function sceneNeeds(text) {
    const t = String(text || '').slice(0, 2000);
    let area = null, ceiling = null;
    const a = new RegExp(`${BOUND}\\s+(\\d{1,5}(?:\\.\\d+)?)\\s*${AREA_UNIT}`, 'i').exec(t);
    if (a) area = { value: Number(a[2]), unit: a[3], m2: toM2(Number(a[2]), a[3]), text: a[0] };
    const c1 = new RegExp(`${BOUND}\\s+(\\d{1,3}(?:\\.\\d+)?)\\s*${LEN_UNIT}\\s+(?:high\\s+)?ceilings?`, 'i').exec(t);
    const c2 = new RegExp(`ceilings?\\s+(?:of\\s+)?${BOUND}\\s+(\\d{1,3}(?:\\.\\d+)?)\\s*${LEN_UNIT}`, 'i').exec(t);
    const c = c1 ? { v: c1[2], u: c1[3], text: c1[0] } : c2 ? { v: c2[2], u: c2[3], text: c2[0] } : null;
    if (c) ceiling = { value: Number(c.v), unit: c.u, m: toM(Number(c.v), c.u), text: c.text };
    const words = ['window', 'door', 'entrance', 'stair', 'island', 'balcony', 'garden', 'yard', 'fireplace', 'skylight', 'elevator', 'quiet'];
    const lower = t.toLowerCase();
    const mentions = words.filter((w) => new RegExp(`\\b${w}s?\\b`).test(lower));
    return { area, ceiling, mentions };
  }

  // ---- fit breakdown for one scene and one candidate (frame + property + logistics) ----
  // input: { scene:{heading,description}, cand, built:{trucks,cars,require_available}|null, mode }
  function fitCheck(input) {
    const { scene, cand, built } = input;
    const rows = [];
    if (!cand) return { rows: [{ kind: 'unknown', label: 'No frame', detail: 'This scene has no assigned location frame, so nothing can be checked.', source: '' }],
      summary: { conflicts: 0, unknowns: 1, estimates: 0, matches: 0 }, similarity: null };
    const sh = cand.shot || {}, prop = cand.property || {}, lg = cand.logistics || {};
    const sim = num(sh.score);
    rows.push({ kind: 'similarity', label: 'Looks like your description',
      detail: sim == null ? 'No similarity score supplied.' : `Image similarity ${sim.toFixed(2)}. This ranks how the frame looks against your text. It is not a fact about the room and not a fit score.`,
      source: input.mode === 'mock' ? 'MOCK fixture ranking' : 'Matterport frame retrieval' });
    // availability (CoStar status is authoritative; the legacy boolean is not)
    const av = ['available', 'not_available'].includes(prop.availability_status) ? prop.availability_status : 'unknown';
    const needAv = !!(built && built.require_available);
    if (av === 'unknown') rows.push({ kind: 'unknown', label: 'Listing availability', detail: needAv ? 'You required an available listing, but the source status is unknown. Confirm with the source.' : 'Source status unknown. Not a vacancy or permission statement.', source: 'CoStar status unknown' });
    else if (av === 'not_available') rows.push({ kind: needAv ? 'conflict' : 'info', label: 'Listing availability', detail: needAv ? 'You required an available listing; the source marks it not available.' : 'The source marks it not available.', source: 'CoStar status not_available' });
    else rows.push({ kind: needAv ? 'match' : 'info', label: 'Listing availability', detail: 'Marketed as available by the source. This is not filming permission.', source: 'CoStar status available' });
    // vehicles: use the source's own sufficiency flag; never recompute from partial counts
    const trucks = Math.max(0, num(built && built.trucks) || 0), cars = Math.max(0, num(built && built.cars) || 0);
    if (trucks || cars) {
      const want = `${trucks} truck${trucks === 1 ? '' : 's'} and ${cars} car${cars === 1 ? '' : 's'}`;
      const pst = known(lg.parking_status) ? lg.parking_status : 'unknown';
      const insufficient = (cand.warnings || []).some((w) => w.field === 'parking_capacity' && w.status === 'insufficient');
      if (pst === 'unknown' || (lg.enough_parking !== true && lg.enough_parking !== false && !insufficient))
        rows.push({ kind: 'unknown', label: 'Parking for your vehicles', detail: `You asked for ${want}. Parking capacity is not established by the data. This is not a parking approval.`, source: 'Vexcel parking unknown' });
      else if (lg.enough_parking === false || insufficient)
        rows.push({ kind: 'conflict', label: 'Parking for your vehicles', detail: `You asked for ${want}; the source reports capacity below that (${pst}).`, source: `Vexcel parking ${pst}` });
      else rows.push({ kind: pst === 'measured' ? 'match' : 'estimate', label: 'Parking for your vehicles', detail: `You asked for ${want}; the source says capacity covers that (${pst}).${pst === 'estimated' ? ' Verify on site.' : ''}`, source: `Vexcel parking ${pst}` });
    }
    // numeric needs the user wrote (lower bounds), compared with index room estimates only
    const needs = sceneNeeds(`${scene && scene.heading || ''}. ${scene && scene.description || ''}`);
    const room = (value, need, what, unitOut, mine) => {
      if (value == null) return rows.push({ kind: 'unknown', label: what, detail: `Your text says "${need.text}", but the index has no ${what.toLowerCase()} for this frame. Measure on site.`, source: 'Matterport index: not supplied' });
      const ok = value >= mine;
      rows.push({ kind: ok ? 'estimate' : 'conflict', label: what, detail: `Your text says "${need.text}". The index estimate is ${value.toFixed(1)} ${unitOut}${ok ? ', consistent with that' : ', below that'}. Index estimates are not site measurements.`, source: 'Matterport index estimate' });
    };
    if (needs.area) room(num(sh.room_area_m2), needs.area, 'Floor area', 'm²', needs.area.m2);
    if (needs.ceiling) room(num(sh.ceiling_m), needs.ceiling, 'Ceiling height', 'm', needs.ceiling.m);
    // quiet: only a flagged proximity screen is evidence; empty or unknown never means quiet
    if (needs.mentions.includes('quiet')) {
      const flags = Array.isArray(lg.noise_flags) ? lg.noise_flags.filter((f) => typeof f === 'string').slice(0, 4) : [];
      if (known(lg.noise_status) && flags.length) rows.push({ kind: 'conflict', label: 'Quiet', detail: `You asked for quiet; the proximity screen flags ${flags.join(', ')} (${lg.noise_status}). This is not a sound measurement.`, source: `Vexcel noise ${lg.noise_status}` });
      else rows.push({ kind: 'unknown', label: 'Quiet', detail: 'You asked for quiet. There is no sound measurement, and an empty noise screen does not mean quiet. Listen on site.', source: 'Noise unknown' });
    }
    const visual = needs.mentions.filter((w) => w !== 'quiet');
    if (visual.length) rows.push({ kind: 'unknown', label: 'Details in your script', detail: `Your text mentions ${visual.join(', ')}. Typecast has no data for these; they are judged only through image similarity. Check the frame by eye. There is no criterion-level analysis.`, source: 'Not in the data' });
    const summary = { conflicts: 0, unknowns: 0, estimates: 0, matches: 0 };
    for (const r of rows) { if (r.kind === 'conflict') summary.conflicts++; else if (r.kind === 'unknown') summary.unknowns++; else if (r.kind === 'estimate') summary.estimates++; else if (r.kind === 'match') summary.matches++; }
    return { rows, summary, similarity: sim };
  }
  function fitSummaryText(r) {
    const s = r.summary, bits = [];
    bits.push(`${s.conflicts} conflict${s.conflicts === 1 ? '' : 's'}`, `${s.unknowns} unknown`);
    if (s.estimates || s.matches) bits.push(`${s.estimates + s.matches} consistent${s.estimates ? ' (estimated)' : ''}`);
    return bits.join(' · ');
  }

  // ---- continuity ----
  const TIMES = ['DAWN', 'MORNING', 'DAY', 'AFTERNOON', 'EVENING', 'DUSK', 'NIGHT'];
  function timeOfDay(heading) {
    const m = /(?:\s-\s|\s–\s|,\s)\s*([A-Za-z ]{3,20})\s*$/.exec(String(heading || ''));
    const w = m ? m[1].trim().toUpperCase() : '';
    return TIMES.includes(w) ? w : null;
  }
  // scenes: [{id, number, heading, group, frame:{shot_id,property_id}|null, take:{actors:[...]}|null}]
  // Only scenes the user explicitly put in the same continuity group are compared, consecutive members only.
  function continuity(scenes, takeLabel) {
    const out = {};
    const add = (sid, issue) => { (out[sid] ||= []).push(issue); };
    const groups = {};
    for (const s of scenes) if (s.group) (groups[s.group] ||= []).push(s);
    for (const [g, list] of Object.entries(groups)) {
      for (let i = 1; i < list.length; i++) {
        const p = list[i - 1], q = list[i], tag = `Scenes ${p.number} and ${q.number} (link "${g}")`;
        const both = (issue) => { add(p.id, issue); add(q.id, { ...issue }); };
        if (!p.frame || !q.frame) { both({ level: 'unknown', text: `${tag}: one of them has no assigned frame, so they cannot be compared.`, action: 'Rebuild the plan or choose a location for the uncovered scene.' }); continue; }
        if (p.frame.property_id !== q.frame.property_id)
          both({ level: 'verified', text: `${tag} use different properties (${p.frame.property_id} and ${q.frame.property_id}), but you linked them as one continuous setting.`, action: `Try another location for scene ${q.number} in the same property, or remove the link if they are different places.` });
        else if (p.frame.shot_id !== q.frame.shot_id)
          both({ level: 'unknown', text: `${tag} use the same property but different frames. Positions cannot be compared across frames, so none were.`, action: 'Confirm by eye that both frames show the same room.' });
        const tp = timeOfDay(p.heading), tq = timeOfDay(q.heading);
        if (tp && tq && tp !== tq)
          both({ level: 'potential', text: `${tag} are ${tp} and ${tq}. That may be a time jump or a mismatch.`, action: 'Confirm the time change is intended or fix a heading.' });
        if (p.frame.shot_id === q.frame.shot_id && p.take && q.take) {
          for (const a of p.take.actors) {
            const b = q.take.actors.find((x) => x.name.trim().toLowerCase() === a.name.trim().toLowerCase());
            if (!b) continue;
            const dx = (a.x1 - b.x0) * 16 / 9, dy = a.y1 - b.y0, d = Math.hypot(dx, dy);
            if (d > 0.15) both({ level: 'potential', text: `${tag} share this exact frame. In take ${takeLabel}, ${a.name} ends scene ${p.number} at (${a.x1.toFixed(2)}, ${a.y1.toFixed(2)}) and starts scene ${q.number} at (${b.x0.toFixed(2)}, ${b.y0.toFixed(2)}). That may be a cut or a jump.`, action: `Set ${a.name}'s start in scene ${q.number} to the earlier end point, or keep it if the cut is intended.` });
          }
        }
      }
    }
    return out;
  }

  // ---- on-site checklist, derived only from what is unresolved ----
  function checklist(fit, cont, ctx) {
    const items = [];
    for (const r of (fit && fit.rows) || []) {
      if (r.kind === 'conflict') items.push(`Resolve conflict: ${r.label}. ${r.detail}`);
      else if (r.kind === 'unknown') items.push(`Establish: ${r.label}. ${r.detail}`);
      else if (r.kind === 'estimate') items.push(`Verify the estimate on site: ${r.label}.`);
    }
    for (const c of cont || []) if (c.level !== 'unknown') items.push(`Continuity (${c.level}): ${c.text} ${c.action}`);
    if (ctx && ctx.carried) items.push('Re-stage the carried-over blocking on this exact frame; it was not verified here.');
    items.push('Measure the room and confirm camera positions and clearances on site; the stage is an uncalibrated screen-space rehearsal.');
    return items;
  }

  const api = { sceneNeeds, fitCheck, fitSummaryText, continuity, checklist, timeOfDay, KIND_LABEL };
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TypecastChecks = api;
})(typeof window !== 'undefined' ? window : globalThis);
