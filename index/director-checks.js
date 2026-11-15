'use strict';
// Pure, deterministic checks for the Director's Room: scene-to-location fit evidence, scene continuity,
// and the on-site checklist. No DOM, no network, no model. Every statement is derived only from fields the
// plan response or the user's own text actually supplies; missing data stays "unknown", never "ok".
(function (root) {
  const KIND_LABEL = { conflict: 'Conflict', unknown: 'Unknown', estimate: 'Consistent (estimated)', match: 'Matches', similarity: 'Visual similarity', info: 'Note' };
  const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  const known = (s) => s === 'measured' || s === 'estimated';
  const M2_PER_SQFT = 0.09290304, M_PER_FT = 0.3048;

  // ---- numeric requirements the user wrote in the scene text ----
  // Only simple phrasings are read: "<qualifier> N <area unit>" and "<qualifier> N <length unit> ceiling(s)" (or
  // "ceiling(s) <qualifier> N <length unit>"). Negated or unfamiliar wording such as "not at least" is listed as
  // unread, never turned into a guessed minimum or maximum. All other needs in the script are NOT extracted.
  const QUALS = {
    'not at least': null, 'not at most': null, 'not over': null, 'not under': null, 'not below': null, 'not above': null,
    'not up to': null, 'not minimum': null, 'not maximum': null,
    'no more than': 'le', 'not more than': 'le', 'no less than': 'ge', 'not less than': 'ge',
    'at least': 'ge', 'at most': 'le', 'minimum of': 'ge', 'minimum': 'ge', 'min.': 'ge', 'min': 'ge',
    'maximum of': 'le', 'maximum': 'le', 'max.': 'le', 'max': 'le', 'up to': 'le',
    'more than': 'gt', 'greater than': 'gt', 'less than': 'lt', 'over': 'gt', 'under': 'lt', 'below': 'lt', 'above': 'gt',
  };
  const QUAL_RE = Object.keys(QUALS).sort((x, y) => y.length - x.length).map((k) => k.replace(/\./g, '\\.').replace(/ /g, '\\s+')).join('|');
  const AREA_UNIT = '(m2|m²|sq\\.? ?m|sqm|square met(?:er|re)s?|sq\\.? ?ft|sqft|square feet|square foot)';
  const LEN_UNIT = '(m|meters?|metres?|ft|feet|foot)';
  const opOf = (q) => { const k = q.toLowerCase().replace(/\s+/g, ' '); return Object.prototype.hasOwnProperty.call(QUALS, k) ? QUALS[k] : null; };
  const toM2 = (v, unit) => (/ft|feet|foot/i.test(unit) ? v * M2_PER_SQFT : v);
  const toM = (v, unit) => (/^(ft|feet|foot)$/i.test(unit) ? v * M_PER_FT : v);
  const COMMUNITY_WORDS = ['toilet', 'restroom', 'power', 'water', 'generator', 'ramp', 'accessible', 'wheelchair', 'parking', 'loading'];
  function sceneNeeds(text, domain) {
    const t = String(text || '').slice(0, 2000);
    const area = [], ceiling = [];
    for (const m of t.matchAll(new RegExp(`\\b(${QUAL_RE})\\s+(\\d{1,5}(?:\\.\\d+)?)\\s*${AREA_UNIT}`, 'gi'))) {
      if (area.length < 4) area.push({ op: opOf(m[1]), value: Number(m[2]), unit: m[3], m2: toM2(Number(m[2]), m[3]), text: m[0] });
    }
    const c1 = new RegExp(`\\b(${QUAL_RE})\\s+(\\d{1,3}(?:\\.\\d+)?)\\s*${LEN_UNIT}\\s+(?:high\\s+)?ceilings?`, 'gi');
    const c2 = new RegExp(`ceilings?\\s+(?:of\\s+)?(${QUAL_RE})\\s+(\\d{1,3}(?:\\.\\d+)?)\\s*${LEN_UNIT}`, 'gi');
    for (const re of [c1, c2]) for (const m of t.matchAll(re)) {
      if (ceiling.length < 4) ceiling.push({ op: opOf(m[1]), value: Number(m[2]), unit: m[3], m: toM(Number(m[2]), m[3]), text: m[0] });
    }
    const words = ['window', 'door', 'entrance', 'stair', 'island', 'balcony', 'garden', 'yard', 'fireplace', 'skylight', 'elevator', 'quiet'];
    const lower = t.toLowerCase();
    const mentions = words.concat(domain === 'community' ? COMMUNITY_WORDS : []).filter((w) => new RegExp(`\\b${w}s?\\b`).test(lower));
    return { area, ceiling, mentions };
  }
  const satisfies = (op, have, need) => (op === 'ge' ? have >= need : op === 'gt' ? have > need : op === 'le' ? have <= need : have < need);

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
    const community = input.domain === 'community';
    const needs = sceneNeeds(`${scene && scene.heading || ''}. ${scene && scene.description || ''}`, input.domain);
    const room = (value, need, what, unitOut, mine) => {
      if (need.op == null) return rows.push({ kind: 'unknown', label: what, detail: `Your text says "${need.text}", which Typecast does not read as a minimum or maximum. No comparison was made.`, source: 'Not read from script' });
      if (value == null) return rows.push({ kind: 'unknown', label: what, detail: `Your text says "${need.text}", but the index has no ${what.toLowerCase()} for this frame. Measure on site.`, source: 'Matterport index: not supplied' });
      const ok = satisfies(need.op, value, mine);
      rows.push({ kind: ok ? 'estimate' : 'conflict', label: what, detail: `Your text says "${need.text}". The index estimate is ${value.toFixed(1)} ${unitOut}${ok ? ', consistent with that' : ', does not satisfy that'}. Index estimates are not site measurements.`, source: 'Matterport index estimate' });
    };
    for (const n of needs.area) room(num(sh.room_area_m2), n, 'Floor area', 'm²', n.m2);
    for (const n of needs.ceiling) room(num(sh.ceiling_m), n, 'Ceiling height', 'm', n.m);
    // quiet: only a flagged proximity screen is evidence; empty or unknown never means quiet
    if (needs.mentions.includes('quiet')) {
      const flags = Array.isArray(lg.noise_flags) ? lg.noise_flags.filter((f) => typeof f === 'string').slice(0, 4) : [];
      if (known(lg.noise_status) && flags.length) rows.push({ kind: 'conflict', label: 'Quiet', detail: `You asked for quiet; the proximity screen flags ${flags.join(', ')} (${lg.noise_status}). This is not a sound measurement.`, source: `Vexcel noise ${lg.noise_status}` });
      else rows.push({ kind: 'unknown', label: 'Quiet', detail: 'You asked for quiet. There is no sound measurement, and an empty noise screen does not mean quiet. Listen on site.', source: 'Noise unknown' });
    }
    const visual = needs.mentions.filter((w) => w !== 'quiet');
    if (visual.length) rows.push({ kind: 'unknown', label: community ? 'Details in your needs' : 'Details in your script', detail: `Your text mentions ${visual.join(', ')}. Typecast has no data for these${community ? ' (toilets, power, water, ramps and similar are not in any source it uses)' : ''}; they are judged only through image similarity. Check the frame by eye. There is no criterion-level analysis.`, source: 'Not in the data' });
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
    // User text (group tags, imported scene ids) is used as a key: Map and a null-prototype object keep 'constructor' and '__proto__' ordinary.
    const out = Object.create(null);
    const add = (sid, issue) => { (out[sid] ||= []).push(issue); };
    const groups = new Map();
    for (const s of scenes) if (s.group) { if (!groups.has(s.group)) groups.set(s.group, []); groups.get(s.group).push(s); }
    for (const [g, list] of groups) {
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

  // ---- script intake: plain screenplay headings or the original `HEADING | description` lines ----
  // Pure and deterministic; no model. Nothing is silently dropped: cuts and ignored lines are reported in `notes`,
  // and anything over a limit is an error with a count. Dialogue stays inside the scene description for retrieval
  // and review; no actors or requirements are derived from it.
  const LIMITS = { chars: 60000, scenes: 8, heading: 120, description: 600 };
  const HEADING_RE = /^\s*(?:\d{1,3}[A-Z]?\s+)?(?:INT\.\s*\/\s*EXT\.|INT\/EXT\.?|I\/E\.?|INT\.|EXT\.)(?:\s+|$)/;
  const CUE_RE = /^[A-Z][A-Z0-9 .'()-]{1,30}$/;
  const clean = (t) => String(t).replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim();
  function cut(text, max, notes, what) {
    if (text.length <= max) return { text, truncated: false };
    notes.push(`${what} was cut from ${text.length} to ${max} characters.`);
    return { text: text.slice(0, max), truncated: true };
  }
  function legacyScenes(lines, notes) {
    if (lines.length > LIMITS.scenes) return { error: `Max ${LIMITS.scenes} scenes (found ${lines.length}).` };
    const scenes = [];
    for (let i = 0; i < lines.length; i++) {
      const l = lines[i], p = l.indexOf('|');
      const headingRaw = clean(p < 0 ? l : l.slice(0, p));
      if (!headingRaw) return { error: `Scene ${i + 1} needs a heading before "|".` };
      const h = cut(headingRaw, LIMITS.heading, notes, `Scene ${i + 1} heading`);
      const d = cut(clean(p < 0 ? l : l.slice(p + 1)) || h.text, LIMITS.description, notes, `Scene ${i + 1} description`);
      scenes.push({ id: `s${i + 1}`, heading: h.text, description: d.text, truncated: h.truncated || d.truncated, dialogue_lines: 0 });
    }
    return { scenes };
  }
  function parseScript(text, mode) {
    const notes = [];
    const raw = String(text == null ? '' : text).replace(/\r\n?/g, '\n');
    if (raw.length > LIMITS.chars) return { error: `The text is ${raw.length.toLocaleString('en-US')} characters; the limit is ${LIMITS.chars.toLocaleString('en-US')}. Paste fewer scenes.`, scenes: [], notes };
    const lines = raw.split('\n').map((l) => l.replace(/\s+$/, ''));
    const nonblank = lines.map((l) => l.trim()).filter(Boolean);
    if (!nonblank.length) return { error: mode === 'community' ? 'Add at least one site need.' : 'Add at least one scene line.', scenes: [], notes };
    const finish = (r) => (r.error ? { error: r.error, scenes: [], notes } : { error: null, scenes: r.scenes, notes });
    if (nonblank.every((l) => l.includes('|'))) return finish(legacyScenes(nonblank, notes));
    if (mode === 'community') {
      // Needs are plain paragraphs: a blank line separates sites, the first line names the need. INT./EXT. has no special meaning here.
      const blocks = []; let cur = [];
      for (const l of lines) { if (l.trim()) cur.push(l.trim()); else if (cur.length) { blocks.push(cur); cur = []; } }
      if (cur.length) blocks.push(cur);
      if (blocks.length > LIMITS.scenes) return finish({ error: `Max ${LIMITS.scenes} needs (found ${blocks.length}).` });
      const scenes = blocks.map((b, i) => {
        const h = cut(clean(b[0].split('|')[0]), LIMITS.heading, notes, `Need ${i + 1} title`);
        const d = cut(clean(b.slice(1).join(' ')) || h.text, LIMITS.description, notes, `Need ${i + 1} description`);
        return { id: `s${i + 1}`, heading: h.text, description: d.text, truncated: h.truncated || d.truncated, dialogue_lines: 0 };
      });
      return finish({ scenes });
    }
    // film: screenplay headings
    const isHeading = (l) => l.length <= 200 && HEADING_RE.test(l);
    const at = [];
    lines.forEach((l, i) => { if (isHeading(l.trim())) at.push(i); });
    if (!at.length) {
      if (nonblank.length <= LIMITS.scenes && nonblank.every((l) => l.length <= 200)) {
        notes.push('No INT./EXT. headings found, so each line was read as one scene.');
        return finish(legacyScenes(nonblank, notes));
      }
      return finish({ error: 'No scene headings found. Start each scene with INT. or EXT. (for example "INT. KITCHEN - DAY"), or write one scene per line as "Heading | description".' });
    }
    const before = lines.slice(0, at[0]).filter((l) => l.trim()).length;
    if (before) notes.push(`${before} line${before === 1 ? '' : 's'} before the first heading ${before === 1 ? 'was' : 'were'} not used (title page or notes).`);
    if (at.length > LIMITS.scenes) return finish({ error: `Max ${LIMITS.scenes} scenes (found ${at.length}). Remove or merge scenes; nothing was dropped.` });
    const scenes = at.map((start, k) => {
      const end = k + 1 < at.length ? at[k + 1] : lines.length, head = lines[start].trim(), p = head.indexOf('|');
      const bodyLines = lines.slice(start + 1, end).map((l) => l.trim());
      const headRaw = clean(p < 0 ? head : head.slice(0, p));
      const h = cut(headRaw, LIMITS.heading, notes, `Scene ${k + 1} heading`);
      const bodyText = clean([p < 0 ? '' : head.slice(p + 1), ...bodyLines].join(' '));
      const d = cut(bodyText || h.text, LIMITS.description, notes, `Scene ${k + 1} description`);
      let cues = 0;
      bodyLines.forEach((l, i) => { if (CUE_RE.test(l) && !HEADING_RE.test(l) && bodyLines[i + 1] && !CUE_RE.test(bodyLines[i + 1])) cues++; });
      return { id: `s${k + 1}`, heading: h.text, description: d.text, truncated: h.truncated || d.truncated, dialogue_lines: cues };
    });
    return finish({ scenes });
  }

  // ---- community planning: coordinator checks are human-reported, unknown by default, never source facts ----
  const COMMUNITY_CHECKS = [
    { key: 'permission', label: 'Owner permission and access' },
    { key: 'capacity', label: 'Verified occupancy and capacity' },
    { key: 'exits', label: 'Exits and fire inspection' },
    { key: 'access', label: 'Accessibility' },
    { key: 'toilets', label: 'Toilets' },
    { key: 'utilities', label: 'Power and water' },
    { key: 'hazards', label: 'Current hazards and site condition' },
  ];
  const CHECK_STATE_LABEL = { unknown: 'Not checked (unknown)', ok: 'Reported OK by the coordinator', issue: 'Reported problem' };
  const isState = (v) => v === 'unknown' || v === 'ok' || v === 'issue';
  const textOf = (v, max) => String(v == null ? '' : v).replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);
  const countOf = (v) => { if (v == null || v === '') return null; const n = Number(v); return Number.isInteger(n) && n >= 0 && n <= 100000 ? n : null; };
  function checkState(site, key) { const c = site && site.checks && site.checks[key]; return c && isState(c.state) ? c.state : 'unknown'; }
  // How many of the seven mandatory checks are still unknown. "Reported OK" never means verified or approved.
  function communityCounts(site) {
    let unknown = 0, ok = 0, issue = 0;
    for (const c of COMMUNITY_CHECKS) { const s = checkState(site, c.key); if (s === 'ok') ok++; else if (s === 'issue') issue++; else unknown++; }
    return { unknown, ok, issue, total: COMMUNITY_CHECKS.length };
  }
  function communityStatusText(site) {
    const k = communityCounts(site);
    return `Needs verification · ${k.unknown} of ${k.total} checks unknown${k.issue ? ` · ${k.issue} reported problem${k.issue === 1 ? '' : 's'}` : ''}${k.ok ? ` · ${k.ok} reported OK by you (not verified)` : ''}`;
  }

  const api = { COMMUNITY_CHECKS, CHECK_STATE_LABEL, isState, textOf, countOf, checkState, communityCounts, communityStatusText, parseScript, LIMITS, sceneNeeds, fitCheck, fitSummaryText, continuity, checklist, timeOfDay, KIND_LABEL };
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.TypecastChecks = api;
})(typeof window !== 'undefined' ? window : globalThis);
