'use strict';
const $ = (id) => document.getElementById(id);
const POSES = ['stand', 'sit', 'walk'];
const BADGE = 'UNCALIBRATED SCREEN-SPACE REHEARSAL · GEOMETRIC FIT UNKNOWN';
// Replace with the repo's original demo script text if it differs.
const DEMO = [
  'INT. KITCHEN - DAY | Warm kitchen with wood cabinets; two sisters prepare a meal',
  'INT. LIVING ROOM - DAY | Bright living room with a sofa and large windows; Mara rehearses a speech',
  'INT. OFFICE CORRIDOR - NIGHT | A security guard walks a long empty hallway, checking each locked door',
].join('\n');
const S = { rev: 0, scenes: [], resp: null, planIdx: 0, planBusy: false, sceneId: null, variant: 'A', forbidden: [], edits: {},
  frameChange: {}, frameOverrides: {}, importReview: [], actorIdx: 0, imgs: {}, pending: null, undo: null, gen: { ctrl: null, tok: 0 },
  play: { on: false, acc: 0, start: 0, raf: 0, q: [], total: 0 } };

function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'text') n.textContent = v; else if (k === 'class') n.className = v; else n.setAttribute(k, v);
  }
  n.append(...kids.filter((c) => c != null));
  return n;
}
function status(msg, err = false) { const s = $('status'); s.textContent = msg; s.classList.toggle('err', err); }
const clamp = (v, lo, hi, d) => { if (v == null || v === '') return d; const n = Number(v); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d; };
const r3 = (v) => Math.round(v * 1000) / 1000;
const clone = (o) => JSON.parse(JSON.stringify(o));
const fmt = (v) => (typeof v === 'number' ? v.toFixed(3) : 'unknown');
const count = (v) => (Array.isArray(v) ? v.length : v ?? 'unknown');

// ---------- data access ----------
const plan = () => (S.resp && S.resp.plans[S.planIdx]) || null;
const assignFor = (sid) => {
  const a = (plan()?.assignments || []).find((x) => x.scene_id === sid);
  const chosen = S.frameOverrides[`${S.planIdx}::${sid}`];
  return a ? (chosen ? { ...a, shot_id: chosen, manual_frame: true } : a) : null;
};
function candFor(sid, shotId) {
  const sc = S.resp?.scenes?.find((s) => s.id === sid);
  return sc?.candidates?.find((c) => c.shot?.shot_id === shotId) || null;
}
const keyOf = (sid) => { const a = assignFor(sid); return a ? `${sid}::${a.shot_id}` : null; };
const blankShot = () => ({ duration_sec: 5, dialogue: '', actors: [] });
function shotData(sid, v = S.variant) {
  const k = keyOf(sid); if (!k) return null;
  S.edits[k] ||= { A: blankShot(), B: blankShot() };
  return S.edits[k][v];
}
const hasWork = (e) => !!e && ['A', 'B'].some((v) => e[v].actors.length || e[v].dialogue || e[v].duration_sec !== 5);
const assignMap = () => Object.fromEntries((plan()?.assignments || []).map((a) => [a.scene_id, a.shot_id]));
function noteFrameChanges(prev) {
  for (const [sid, old] of Object.entries(prev)) {
    const a = assignFor(sid);
    if (a && a.shot_id !== old && hasWork(S.edits[`${sid}::${old}`]) && !hasWork(S.edits[`${sid}::${a.shot_id}`]))
      S.frameChange[sid] = { from: old, to: a.shot_id };
  }
}
function sanitizeShot(s) {
  const actors = (Array.isArray(s?.actors) ? s.actors : []).slice(0, 3).map((a, i) => {
    const x0 = r3(clamp(a?.x0, 0, 1, 0.5)), y0 = r3(clamp(a?.y0, 0, 1, 0.85));
    return { id: String(a?.id ?? `a${i + 1}`).slice(0, 32), name: String(a?.name ?? '').slice(0, 24) || `Actor ${i + 1}`,
      pose: POSES.includes(a?.pose) ? a.pose : 'stand', x0, y0,
      x1: r3(clamp(a?.x1, 0, 1, x0)), y1: r3(clamp(a?.y1, 0, 1, y0)), scale: clamp(a?.scale, 0.3, 2, 1) };
  });
  return { duration_sec: clamp(s?.duration_sec, 1, 30, 5), dialogue: String(s?.dialogue ?? '').slice(0, 800), actors };
}

// ---------- backend ----------
function parseScenes() {
  const lines = $('script').value.split('\n').map((l) => l.trim()).filter(Boolean);
  if (!lines.length) throw new Error('Add at least one scene line.');
  if (lines.length > 8) throw new Error(`Max 8 scenes (found ${lines.length}).`);
  return lines.map((l, i) => {
    const p = l.indexOf('|');
  const heading = (p < 0 ? l : l.slice(0, p)).trim().slice(0, 120);
    if (!heading) throw new Error(`Scene ${i + 1} needs a heading before "|".`);
    return { id: `s${i + 1}`, heading, description: (p < 0 ? heading : l.slice(p + 1)).trim().slice(0, 600) || heading };
  });
}
async function api(path, body, signal) {
  const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });
  let data = null;
  try { data = await r.json(); } catch { /* non-JSON body */ }
  if (!r.ok) {
    const d = data && (data.detail ?? data.error);
    throw new Error(d ? (typeof d === 'string' ? d : JSON.stringify(d)).slice(0, 300) : `HTTP ${r.status}`);
  }
  if (!data || typeof data !== 'object') throw new Error('Empty or non-JSON response');
  return data;
}
function busy(on) {
  S.planBusy = on;
  $('impProject').disabled = on;
  $('build').disabled = on; $('reject').disabled = on || !assignFor(S.sceneId);
  $('lookAround').disabled = on || !assignFor(S.sceneId);
  $('planSel').disabled = on || !(S.resp?.plans.length);
  const frameSelect = $('framePicker').querySelector('select'); if (frameSelect) frameSelect.disabled = on;
  $('gen').disabled = on || !!S.gen.ctrl;
}
// Rejections remain authoritative even if a stale or faulty backend returns them (or no backend answers).
function applyForbidden(data) {
  const forbidden = new Set(S.forbidden);
  data.scenes = data.scenes.map((scene) => ({ ...scene,
    candidates: (scene.candidates || []).filter((c) => !forbidden.has(c.shot?.property_id)) }));
  let changed = false;
  data.plans = data.plans.map((p) => {
    const removed = (p.assignments || []).filter((a) => forbidden.has(a.property_id));
    if (!removed.length && !(p.property_ids || []).some((id) => forbidden.has(id))) return p;
    changed = true;
    // The solver publishes property_ids and a numeric locations count; rederive both from what remains.
    const assignments = (p.assignments || []).filter((a) => !forbidden.has(a.property_id));
    const property_ids = [...new Set(assignments.map((a) => a.property_id))].sort();
    return { ...p, assignments, property_ids, locations: property_ids.length,
      uncovered_scene_ids: [...new Set([...(p.uncovered_scene_ids || []), ...removed.map((a) => a.scene_id)])],
      company_moves: null, mean_similarity: null };
  });
  if (changed && 'optimal_within_pool' in data) data.optimal_within_pool = false;
  if (Array.isArray(data.pool_properties)) data.pool_properties = data.pool_properties.filter((id) => !forbidden.has(id));
  return data;
}
async function build(reuse) {
  if (S.planBusy) return;
  stopPlay(); cancelGen(); clearPending();
  let scenes;
  try { scenes = reuse ? S.scenes : parseScenes(); } catch (e) { return status(e.message, true); }
  const body = { scenes, max_locations: clamp($('maxLoc').value, 1, 4, 3), forbidden_property_ids: [...S.forbidden],
    require_available: $('reqAvail').checked, trucks: Math.floor(clamp($('trucks').value, 0, 20, 0)),
    cars: Math.floor(clamp($('cars').value, 0, 50, 0)) };
  const prev = assignMap();
  busy(true); status('Requesting production plan from backend…');
  try {
    const data = await api('/api/production/plan', body);
    if (!Array.isArray(data.scenes) || !Array.isArray(data.plans)) throw new Error('Malformed plan response');
    applyForbidden(data);
    S.scenes = scenes; S.resp = data; S.planIdx = 0; S.frameOverrides = {};
    if (!scenes.some((s) => s.id === S.sceneId)) { S.sceneId = scenes[0].id; S.actorIdx = 0; }
    noteFrameChanges(prev); renderAll();
    if (data.plans.length) status(`${data.plans.length} candidate plan(s) returned. Candidates are not verified shootability.`);
    else status('Backend returned no plan for these constraints. Your staging is kept.', true);
  } catch (e) {
    if (reuse && S.resp && S.forbidden.length) {
      // A rejection is the user's decision: never keep showing the rejected location because the replan failed.
      applyForbidden(S.resp); renderAll();
      status(`Replan failed: ${e.message}. The rejected location was removed locally; affected scenes are uncovered until a replan succeeds.`, true);
    } else status(`Plan request failed: ${e.message}`, true);
  } finally { busy(false); }
}
function reject() {
  const a = assignFor(S.sceneId);
  if (!a) return status('This scene has no assigned location to reject.', true);
  if (!S.forbidden.includes(a.property_id)) S.forbidden.push(a.property_id);
  build(true);
}

// ---------- images + drawing ----------
function img(shotId) {
  if (S.imgs[shotId]) return S.imgs[shotId];
  const r = { el: new Image(), ok: false, err: false };
  const refresh = () => { if (!S.play.on) { if (S.play.acc > 0) frameAt(S.play.acc); else draw(); } };
  r.el.onload = () => { r.ok = true; refresh(); };
  r.el.onerror = () => { r.err = true; refresh(); };
  r.el.src = `/image/${encodeURIComponent(shotId)}`;
  return (S.imgs[shotId] = r);
}
function provText(sid) {
  const i = S.scenes.findIndex((s) => s.id === sid), a = assignFor(sid), c = a && candFor(sid, a.shot_id);
  return `Scene ${i + 1} · Variant ${S.variant} · Matterport · property ${a ? safeId(a.property_id).slice(0, 12) : 'none'}`;
}
function wrap(ctx, text, max) {
  const out = []; let line = '';
  for (const w of String(text).split(/\s+/)) {
    const t = line ? `${line} ${w}` : w;
    if (ctx.measureText(t).width > max && line) { out.push(line); line = w; } else line = t;
  }
  if (line) out.push(line);
  if (out.length > 2) out[1] += ' …';
  return out.slice(0, 2);
}
function figure(ctx, H, px, py, a, t, sel) {
  const u = (a.scale * 0.34 * H) / 7.6, hip = py - (a.pose === 'sit' ? 2 : 3) * u, neck = hip - 3 * u;
  ctx.save(); ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = Math.max(2, u * 0.5);
  ctx.strokeStyle = ctx.fillStyle = sel ? '#c6f432' : '#ffb547';
  ctx.shadowColor = 'rgba(0,0,0,.85)'; ctx.shadowBlur = 8; ctx.beginPath();
  if (a.pose === 'sit') { ctx.moveTo(px, hip); ctx.lineTo(px + 1.7 * u, hip); ctx.lineTo(px + 1.7 * u, py); } else {
    const sw = a.pose === 'walk' ? (t == null ? 0.9 : Math.sin(t * 7) * 1.1) * u : 0.45 * u;
    ctx.moveTo(px - sw, py); ctx.lineTo(px, hip); ctx.lineTo(px + sw, py);
  }
  ctx.moveTo(px, hip); ctx.lineTo(px, neck);
  const arm = a.pose === 'walk' && t != null ? Math.sin(t * 7 + Math.PI) * u : 0;
  ctx.moveTo(px - 1.2 * u + arm, hip - u); ctx.lineTo(px, neck + 0.4 * u); ctx.lineTo(px + 1.2 * u - arm, hip - u);
  ctx.moveTo(px + 0.8 * u, neck - 0.8 * u); ctx.arc(px, neck - 0.8 * u, 0.8 * u, 0, Math.PI * 2);
  ctx.stroke(); ctx.shadowBlur = 4; ctx.textAlign = 'center';
  ctx.font = `600 ${Math.max(14, u * 1.1)}px system-ui`; ctx.fillText(a.name, px, neck - 2 * u, 260);
  ctx.restore();
}
function drawStage(ctx, W, H, o) {
  ctx.save(); ctx.fillStyle = '#0b0807'; ctx.fillRect(0, 0, W, H);
  if (o.imgEl) {
    const iw = o.imgEl.naturalWidth || o.imgEl.width, ih = o.imgEl.naturalHeight || o.imgEl.height, s = Math.min(W / iw, H / ih);
    ctx.drawImage(o.imgEl, (W - iw * s) / 2, (H - ih * s) / 2, iw * s, ih * s);
  } else {
    ctx.fillStyle = '#b49c86'; ctx.font = '28px system-ui'; ctx.textAlign = 'center';
    ctx.fillText(o.missing || 'No frame', W / 2, H / 2, W - 80);
  }
  const sh = o.shot;
  if (sh) sh.actors.forEach((a, i) => {
    const k = o.t == null ? 0 : clamp(o.t / sh.duration_sec, 0, 1, 0), moved = a.x1 !== a.x0 || a.y1 !== a.y0;
    if (o.editing && (moved || i === o.sel)) {
      ctx.strokeStyle = 'rgba(198,244,50,.85)'; ctx.lineWidth = 3; ctx.setLineDash([10, 8]); ctx.beginPath();
      ctx.moveTo(a.x0 * W, a.y0 * H); ctx.lineTo(a.x1 * W, a.y1 * H); ctx.stroke(); ctx.setLineDash([]);
      ctx.beginPath(); ctx.arc(a.x1 * W, a.y1 * H, 13, 0, Math.PI * 2); ctx.stroke();
    }
    figure(ctx, H, (a.x0 + (a.x1 - a.x0) * k) * W, (a.y0 + (a.y1 - a.y0) * k) * H, a, o.t, o.editing && i === o.sel);
  });
  ctx.fillStyle = 'rgba(10,7,5,.75)'; ctx.fillRect(0, 0, W, 44);
  ctx.textAlign = 'left'; ctx.font = '600 17px system-ui'; ctx.fillStyle = '#ffb547'; ctx.fillText(BADGE, 16, 28, W * 0.44);
  ctx.textAlign = 'right'; ctx.font = '15px ui-monospace,monospace'; ctx.fillStyle = '#f4e8d8'; ctx.fillText(o.prov, W - 16, 28, W * 0.52);
  if (sh && sh.dialogue) {
    ctx.font = '24px Georgia,serif'; const lines = wrap(ctx, sh.dialogue, W - 160), bh = 20 + lines.length * 32;
    ctx.fillStyle = 'rgba(10,7,5,.75)'; ctx.fillRect(0, H - bh, W, bh); ctx.fillStyle = '#fff6e8'; ctx.textAlign = 'center';
    lines.forEach((l, i) => ctx.fillText(l, W / 2, H - bh + 36 + i * 32, W - 120));
  }
  ctx.restore();
}
function liveArgs(sid, t) {
  const a = assignFor(sid), im = a ? img(a.shot_id) : null;
  const missing = !S.resp ? 'Build a plan to load real indexed frames' : !a ? 'Uncovered scene: no location assigned'
    : im.err ? `Indexed image unavailable (${a.shot_id})` : 'Loading indexed frame…';
  return { imgEl: im && im.ok ? im.el : null, missing, prov: provText(sid), shot: a ? shotData(sid) : null, t, editing: t == null, sel: S.actorIdx };
}
function draw(t = null, sid = S.sceneId) { const c = $('stage'); drawStage(c.getContext('2d'), c.width, c.height, liveArgs(sid, t)); }

// ---------- playback ----------
function play() {
  if (S.play.on) return;
  const q = S.scenes.filter((s) => assignFor(s.id)).map((s) => ({ sid: s.id, dur: shotData(s.id).duration_sec }));
  if (!q.length) return status('Nothing to play: no scene has an assigned frame.', true);
  const total = q.reduce((n, x) => n + x.dur, 0);
  if (S.play.acc >= total) S.play.acc = 0;
  Object.assign(S.play, { on: true, q, total, start: performance.now() });
  status(`Playing variant ${S.variant}.`);
  const tick = (now) => {
    if (!S.play.on) return;
    const t = Math.min(S.play.acc + (now - S.play.start) / 1000, total);
    frameAt(t);
    if (t >= total) { S.play.on = false; S.play.acc = total; status('Playback finished.'); return; }
    S.play.raf = requestAnimationFrame(tick);
  };
  S.play.raf = requestAnimationFrame(tick);
}
function frameAt(t) {
  let rem = t;
  for (const [i, x] of S.play.q.entries()) {
    if (rem <= x.dur || i === S.play.q.length - 1) { draw(Math.min(rem, x.dur), x.sid); highlight(x.sid); break; }
    rem -= x.dur;
  }
  $('prog').value = S.play.total ? t / S.play.total : 0;
  $('clock').textContent = `${t.toFixed(1)}s / ${S.play.total.toFixed(1)}s`;
}
function pause() {
  if (!S.play.on) return;
  cancelAnimationFrame(S.play.raf); S.play.on = false;
  S.play.acc = Math.min(S.play.total, S.play.acc + (performance.now() - S.play.start) / 1000); status('Paused.');
}
function stopPlay() {
  endDrag();
  cancelAnimationFrame(S.play.raf); S.play.on = false; S.play.acc = 0;
  $('prog').value = 0; $('clock').textContent = '0.0s'; highlight(null);
}
function highlight(sid) { for (const b of $('timeline').querySelectorAll('button')) b.classList.toggle('now', b.dataset.sid === sid); }

// ---------- rendering ----------
function kv(title, obj) {
  const sec = el('section', { class: 'ev' }, el('h4', { text: title })), dl = el('dl');
  const ents = obj && typeof obj === 'object' ? Object.entries(obj).slice(0, 16) : [];
  if (!ents.length) dl.append(el('dt', { text: 'record' }), el('dd', { class: 'unk', text: 'unknown (none returned)' }));
  for (const [k, v] of ents) dl.append(el('dt', { text: k }), el('dd', { class: v == null ? 'unk' : '',
    text: v == null ? 'unknown' : typeof v === 'object' ? JSON.stringify(v).slice(0, 140) : String(v) }));
  sec.append(dl); return sec;
}
// Export an explicit evidence summary, never provider rows, contact details or filesystem paths.
function pickFields(obj, keys) {
  return obj ? Object.fromEntries(keys.map((k) => [k, typeof obj[k] === 'number' || typeof obj[k] === 'boolean' ? obj[k] : null])) : null;
}
function safeId(value) {
  return typeof value === 'string' && /^[\w.:-]{1,120}$/.test(value) && !value.includes('..') &&
    !/^(?:sk-|api[_-]?key|bearer[.:-])/i.test(value) ? value : 'unknown';
}
function evidenceSummary(sid) {
  const a = assignFor(sid), c = a && candFor(sid, a.shot_id), sh = c?.shot;
  if (!a) return null;
  const availability = ['available', 'not_available'].includes(c?.property?.availability_status)
    ? c.property.availability_status : 'unknown';
  const metricStatus = (v) => ['measured', 'estimated'].includes(v) ? v : 'unknown';
  const parking = metricStatus(c?.logistics?.parking_status), walk = metricStatus(c?.logistics?.walk_status);
  return { frame: { shot_id: safeId(a.shot_id), model_id: safeId(sh?.model_id), sweep_id: safeId(sh?.sweep_id), property_id: safeId(a.property_id),
      ...pickFields(sh, ['heading_deg', 'score', 'measure_on_site']), plan_score: typeof a.score === 'number' ? a.score : null },
    room: pickFields(sh, ['room_area_m2', 'ceiling_m', 'depth_m']),
    property: { ...pickFields(c?.property, ['year_built', 'size_sqft']),
      available: availability === 'unknown' ? null : availability === 'available', availability_status: availability },
    logistics: { ...pickFields(c?.logistics, ['estimated']),
      ...pickFields(parking === 'unknown' ? {} : c?.logistics, ['truck_spaces', 'car_spaces', 'parking_area_m2', 'enough_parking']),
      ...pickFields(walk === 'unknown' ? {} : c?.logistics, ['walk_m']),
      parking_status: parking, walk_status: walk, noise_status: metricStatus(c?.logistics?.noise_status) },
    warnings: (c?.warnings || []).map((w) => ({ source: safeId(w.source),
      field: w.field === 'property_id/model_id' ? w.field : safeId(w.field),
      status: ['matched', 'conflict', 'insufficient', 'estimated', 'measured', 'unknown', 'unavailable'].includes(w.status) ? w.status : 'unknown' })) };
}
function warningMeaning(w) {
  if (w.field === 'property_id/model_id') return w.status === 'matched'
    ? 'Exact CoStar property-to-Matterport model match. This property identity groups scenes into fewer locations.'
    : w.status === 'conflict' ? 'IDs conflict with the supplied mapping; excluded from candidate plans.'
    : 'Property-to-model association could not be confirmed from the supplied mapping.';
  if (w.field === 'parking_capacity') return w.status === 'insufficient'
    ? 'Estimated capacity is below the requested vehicles; excluded from candidate plans.'
    : w.status === 'estimated' ? 'Capacity is estimated; verify before the shoot.' : 'Parking capacity is unknown; this is not a parking approval.';
  if (w.field === 'geometry') return 'Room geometry is incomplete or estimated. Rehearsal positions do not establish physical clearance.';
  if (w.field === 'property') return 'Property details are unavailable. Listing availability and filming permission are not established.';
  return 'Review this source field before production.';
}
function evidenceNodes(sid, summary = evidenceSummary(sid)) {
  const f = document.createDocumentFragment(), a = summary;
  if (!a) { f.append(el('p', { class: 'unk', text: S.resp ? 'Uncovered in this plan: no location assigned.' : 'No plan yet.' })); return f; }
  f.append(kv('Frame · Matterport index', a.frame),
    kv('Room metrics · index estimate, not calibrated to stage', a.room),
    kv('Property · CoStar', a.property), kv('Logistics · Vexcel', a.logistics));
  const w = el('section', { class: 'ev' }, el('h4', { text: 'Source warnings' })), ws = a.warnings;
  if (!ws.length) w.append(el('p', { class: 'meta', text: 'No warnings returned. Absence of a warning is not verification.' }));
  ws.forEach((x) => w.append(el('p', { class: 'warn', text: `[${x.source}] ${x.field} · ${x.status}: ${warningMeaning(x)}` })));
  f.append(w); return f;
}
function renderPlan() {
  const sel = $('planSel'), plans = S.resp?.plans || []; sel.replaceChildren();
  plans.forEach((p, i) => {
    const cov = S.scenes.length - (p.uncovered_scene_ids || []).length;
    sel.append(el('option', { value: String(i), text: `Plan ${i + 1}: ${cov}/${S.scenes.length} covered · ${p.company_moves ?? '?'} moves · mean sim ${fmt(p.mean_similarity)}` }));
  });
  sel.value = String(S.planIdx); sel.disabled = S.planBusy || !plans.length;
  $('planMeta').textContent = S.resp ? `Mode ${S.resp.mode ?? 'unknown'} · ${count(S.resp.evaluated_subsets)} subsets evaluated · pool ${count(S.resp.pool_properties)} properties. Mean sim is raw similarity, not shootability.` : 'No plan yet.';
  $('forbidden').textContent = S.forbidden.length ? `Rejected: ${S.forbidden.join(', ')}` : 'No rejected locations.';
  $('clearRej').disabled = !S.forbidden.length;
}
function sceneButton(s, i, cls, ...kids) {
  const b = el('button', { type: 'button', 'data-sid': s.id }, ...kids);
  if (s.id === S.sceneId) b.setAttribute('aria-current', 'true');
  b.addEventListener('click', () => selectScene(s.id));
  return el('li', { class: cls }, b);
}
function renderRail() {
  $('rail').replaceChildren(...S.scenes.map((s, i) => { const a = assignFor(s.id);
    return sceneButton(s, i, '', el('strong', { text: `${i + 1}. ${s.heading}` }), el('small', { text: s.description || '(no description)' }),
      el('span', { class: a ? 'loc' : 'loc none', text: a ? `property ${a.property_id} · frame ${a.shot_id}` : S.resp ? 'uncovered' : 'not planned' })); }));
}
function renderTimeline() {
  $('timeline').replaceChildren(...S.scenes.map((s, i) => { const sh = assignFor(s.id) ? shotData(s.id) : null;
    return sceneButton(s, i, '', el('strong', { text: `${i + 1} · ${sh ? `${sh.duration_sec}s` : 'skipped'}` }), el('span', { text: s.heading }),
      el('small', { text: sh ? `${sh.actors.length} actor(s) · var ${S.variant}` : 'no frame; not played' })); }));
}
function syncActor(a) {
  $('aName').value = a ? a.name : ''; $('aPose').value = a ? a.pose : 'stand'; $('aScale').value = a ? a.scale : '';
  for (const f of ['x0', 'y0', 'x1', 'y1']) $(`a${f}`).value = a ? a[f].toFixed(2) : '';
}
function renderInspector() {
  const shot = shotData(S.sceneId); $('varLbl').textContent = S.variant; $('shotForm').disabled = !shot;
  $('dur').value = shot ? shot.duration_sec : ''; $('dlg').value = shot ? shot.dialogue : '';
  if (shot && S.actorIdx >= shot.actors.length) S.actorIdx = Math.max(0, shot.actors.length - 1);
  const sel = $('actorSel'); sel.replaceChildren(...(shot?.actors || []).map((a, i) => el('option', { value: String(i), text: a.name })));
  sel.value = String(S.actorIdx); const a = shot?.actors[S.actorIdx];
  $('actorForm').disabled = !a; $('addActor').disabled = !shot || shot.actors.length >= 3; $('delActor').disabled = !a;
  syncActor(a);
}
function renderFrameNotice() {
  const n = $('frameNotice'), fc = S.frameChange[S.sceneId], a = assignFor(S.sceneId); n.replaceChildren();
  if (!fc || !a || a.shot_id !== fc.to) { n.hidden = true; return; }
  const copy = el('button', { type: 'button', text: 'Copy old staging (re-check by eye)' }), fresh = el('button', { type: 'button', text: 'Start fresh' });
  copy.addEventListener('click', () => {
    S.rev++;
    S.edits[`${S.sceneId}::${fc.to}`] = clone(S.edits[`${S.sceneId}::${fc.from}`]); delete S.frameChange[S.sceneId];
    stopPlay(); renderAll(); status('Staging copied. Screen positions carry no geometry; re-stage against the new frame.');
  });
  fresh.addEventListener('click', () => {
    S.rev++;
    stopPlay(); cancelGen(); clearPending(); S.edits[`${S.sceneId}::${fc.to}`] = { A: blankShot(), B: blankShot() };
    delete S.frameChange[S.sceneId]; renderAll();
  });
  n.append(el('p', { text: `Frame changed: ${fc.from} → ${fc.to}. Your staging stays attached to the old frame and was not moved.` }), el('div', { class: 'row' }, copy, fresh));
  n.hidden = false;
}
function renderFrames() {
  const box = $('framePicker'), a = assignFor(S.sceneId); box.replaceChildren();
  if (!a) return;
  const candidates = S.resp.scenes.find((s) => s.id === S.sceneId)?.candidates || [];
  const choices = candidates.filter((c) => c.eligible && c.shot.property_id === a.property_id);
  const label = el('label', { text: 'Frame within assigned property (creative choice)' }), select = el('select', { 'aria-label': 'Frame within assigned property' });
  choices.forEach((c) => select.append(el('option', { value: c.shot.shot_id, text: `${c.shot.shot_id} · similarity ${fmt(c.shot.score)}` })));
  select.value = a.shot_id;
  select.disabled = S.planBusy;
  select.addEventListener('change', () => {
    const prev = assignMap(); S.rev++; stopPlay(); cancelGen(); clearPending();
    S.frameOverrides[`${S.planIdx}::${S.sceneId}`] = select.value;
    noteFrameChanges(prev); renderAll(); status('Manual frame selected within the same property. Plan score still describes the original solver selection.');
  });
  label.append(select); box.append(label);
  if (a.manual_frame) box.append(el('p', { class: 'meta', text: 'Manual frame choice. Plan similarity describes the original solver selection; property budget is unchanged.' }));
}
function renderAll() {
  renderProjectReview();
  renderPlan(); renderRail(); renderTimeline(); renderInspector(); renderFrameNotice(); renderFrames();
  $('evidence').replaceChildren(evidenceNodes(S.sceneId));
  const a = assignFor(S.sceneId), pl = $('planner');
  $('lookAround').disabled = S.planBusy || !a;
  $('reject').disabled = S.planBusy || !a; $('expPack').disabled = !plan(); $('expReel').disabled = !plan() || !!reelCtrl; pl.hidden = !a;
  if (a) pl.href = `/api/plan/${encodeURIComponent(a.shot_id)}?heading=0&focal=35`;
  draw();
}
function invalidateProposal() {
  if (S.gen.ctrl || S.pending) { cancelGen(); clearPending(); status('Staging changed; generate a new proposal to review.'); }
}
function edited() { S.rev++; invalidateProposal(); stopPlay(); draw(); renderTimeline(); }
function selectScene(sid) {
  stopPlay(); cancelGen();
  if (S.pending) { clearPending(); status('Pending proposal discarded because the scene changed.'); }
  S.sceneId = sid; S.actorIdx = 0; renderAll();
}
function setVariant(v) {
  stopPlay(); cancelGen(); clearPending(); S.variant = v;
  $('varA').setAttribute('aria-pressed', String(v === 'A')); $('varB').setAttribute('aria-pressed', String(v === 'B'));
  renderAll();
}
const curActor = () => shotData(S.sceneId)?.actors[S.actorIdx];

// ---------- brainstorm ----------
function setGen(on) { $('gen').disabled = on || S.planBusy; $('gen').textContent = on ? 'Generating…' : 'Generate alternative'; }
function cancelGen() {
  if (S.gen.ctrl) { S.gen.ctrl.abort(); S.gen.ctrl = null; status('Generation cancelled.'); }
  S.gen.tok++; setGen(false);
}
function clearPending() { S.pending = null; $('proposal').hidden = true; }
function diffLines(a, b) {
  const out = [], d = (q) => (q ? `${q.name} ${q.pose} (${q.x0.toFixed(2)},${q.y0.toFixed(2)})→(${q.x1.toFixed(2)},${q.y1.toFixed(2)}) ×${q.scale}` : '(none)');
  if (a.duration_sec !== b.duration_sec) out.push(`Duration: ${a.duration_sec}s → ${b.duration_sec}s`);
  if (a.dialogue !== b.dialogue) out.push(`Dialogue: "${a.dialogue || '(none)'}" → "${b.dialogue || '(none)'}"`);
  for (let i = 0; i < Math.max(a.actors.length, b.actors.length); i++)
    if (d(a.actors[i]) !== d(b.actors[i])) out.push(`Actor ${i + 1}: ${d(a.actors[i])} → ${d(b.actors[i])}`);
  return out.length ? out : ['No changes.'];
}
async function generate() {
  if (S.planBusy) return status('Wait for the new plan before generating a proposal.', true);
  const sid = S.sceneId, shot = shotData(sid), sc = S.scenes.find((s) => s.id === sid);
  if (!shot || !sc) return status('Select a scene with an assigned frame first.', true);
  const instruction = $('instr').value.trim();
  if (!instruction) return status('Type or dictate an instruction first.', true);
  cancelGen(); clearPending();
  const ctrl = new AbortController(), tok = ++S.gen.tok, k = keyOf(sid);
  S.gen.ctrl = ctrl; setGen(true); status('Generating alternative with the model…');
  try {
    const r = await api('/api/production/brainstorm', { instruction: instruction.slice(0, 600), heading: sc.heading, description: sc.description, shot: clone(shot) }, ctrl.signal);
    if (tok !== S.gen.tok || keyOf(S.sceneId) !== k) return;
    if (!r.shot || typeof r.shot !== 'object') throw new Error('model returned no shot');
    S.pending = { k, shot: sanitizeShot(r.shot) };
    $('pSum').textContent = String(r.summary ?? '(no summary)').slice(0, 400);
    $('pNote').textContent = String(r.creative_note ?? '').slice(0, 600);
    $('pDiff').replaceChildren(...diffLines(S.edits[k].B, S.pending.shot).map((t) => el('li', { text: t })));
    $('proposal').hidden = false; status('Proposal ready. Nothing has changed yet; review, then Apply to B or Discard.');
  } catch (e) {
    if (e.name === 'AbortError' || tok !== S.gen.tok) return;
    status(`Brainstorm unavailable: ${e.message}. No changes made.`, true);
  } finally { if (tok === S.gen.tok) { S.gen.ctrl = null; setGen(false); } }
}
function applyB() {
  if (!S.pending || keyOf(S.sceneId) !== S.pending.k) { clearPending(); return status('Proposal no longer matches this scene; discarded.', true); }
  S.rev++; const ed = S.edits[S.pending.k]; S.undo = { k: S.pending.k, prev: clone(ed.B) }; ed.B = clone(S.pending.shot);
  clearPending(); $('undo').disabled = false; stopPlay(); renderAll();
  status(S.variant === 'B' ? 'Applied to variant B.' : 'Applied to variant B. Switch to B to view it.');
}
function undoApply() {
  if (!S.undo || !S.edits[S.undo.k]) return;
  S.rev++;
  S.edits[S.undo.k].B = S.undo.prev; S.undo = null; $('undo').disabled = true; stopPlay(); renderAll(); status('Apply undone.');
}

// ---------- speech (explicit push-to-talk, off by default) ----------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null;
function micOff() { rec = null; $('micStart').disabled = !SR; $('micStop').disabled = true; }
if (!SR) { $('micStart').disabled = true; $('micNote').append(' Speech recognition is not available in this browser; type instead.'); }
$('micStart').addEventListener('click', () => {
  try {
    rec = new SR(); rec.lang = 'en-US'; rec.interimResults = false; rec.continuous = true;
    rec.onresult = (e) => {
      let t = ''; for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) t += e.results[i][0].transcript;
      if (t) $('instr').value = `${$('instr').value} ${t}`.trim().slice(0, 600);
    };
    rec.onerror = (e) => status(`Mic error (${e.error}). Type your instruction instead.`, true);
    rec.onend = micOff; rec.start();
    $('micStart').disabled = true; $('micStop').disabled = false; status('Listening. Press Stop mic, then edit the transcript before generating.');
  } catch (e) { status(`Mic unavailable: ${e.message}. Type instead.`, true); micOff(); }
});
$('micStop').addEventListener('click', () => rec && rec.stop());

// ---------- export ----------
function download(blob, name) {
  const u = URL.createObjectURL(blob), a = el('a', { href: u, download: name });
  document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 2000);
}
async function dataUrl(path) {
  const r = await fetch(path, { credentials: 'same-origin' });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const b = await r.blob();
  if (!/^image\/(png|jpeg|webp|gif)$/.test(b.type)) throw new Error('response is not a raster image');
  return new Promise((res, rej) => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.onerror = () => rej(new Error('read failed')); fr.readAsDataURL(b); });
}
const loadImg = (src) => new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => rej(new Error('decode failed')); i.src = src; });
const PACK_CSS = 'body{font:14px/1.5 Georgia,serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a120c}section.scene{break-inside:avoid;border-top:2px solid #c98a1c;padding:1rem 0}img{width:100%;border:1px solid #ccc}.meta{color:#6b5847;font-size:12px}dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:12px}dt{color:#6b5847}dd{margin:0}.unk{color:#b3261e;font-style:italic}.warn{font-size:12px}h4{margin:.6rem 0 .2rem}';
function exportSnapshot() {
  const p = plan();
  return clone({ app: 'Typecast Director', exported_at: new Date().toISOString(), variant: S.variant, plan_index: S.planIdx,
    honesty: 'Candidate plans only. Uncalibrated screen-space rehearsal; geometric fit unknown. Plan score describes original solver frames; manual frame choices retain the assigned property.',
    source_mode: S.resp?.mode ?? 'unknown', locations: count(p?.locations), company_moves: p?.company_moves ?? null, mean_similarity: p?.mean_similarity ?? null,
    review_needed: S.importReview,
    scenes: S.scenes.map((s) => ({ ...s, evidence: evidenceSummary(s.id),
      manual_frame: !!assignFor(s.id)?.manual_frame, staging: assignFor(s.id) ? sanitizeShot(shotData(s.id)) : null,
      variants: assignFor(s.id) ? { A: sanitizeShot(shotData(s.id, 'A')), B: sanitizeShot(shotData(s.id, 'B')) } : null,
      provenance_label: provText(s.id) })) });
}
async function exportPack() {
  const p = plan(); if (!p) return status('Build a plan first.', true);
  const snapshot = exportSnapshot();
  stopPlay(); $('expPack').disabled = true; status('Building shoot pack from real indexed images…');
  try {
    const doc = document.implementation.createHTMLDocument('Typecast shoot pack');
    const E = (tag, text, cls) => { const n = doc.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
    const cs = doc.createElement('meta'); cs.setAttribute('charset', 'utf-8');
    const csp = doc.createElement('meta'); csp.setAttribute('http-equiv', 'Content-Security-Policy');
    csp.setAttribute('content', "default-src 'none'; img-src data:; style-src 'unsafe-inline'");
    const st = doc.createElement('style'); st.textContent = PACK_CSS; doc.head.prepend(cs, csp); doc.head.append(st);
    doc.body.append(E('h1', 'Typecast shoot pack'),
      E('p', `Generated ${snapshot.exported_at} · Variant ${snapshot.variant} · Plan ${snapshot.plan_index + 1}: ${snapshot.locations} location(s), ${snapshot.company_moves ?? 'unknown'} company move(s), mean original-plan similarity ${fmt(snapshot.mean_similarity)} · mode ${snapshot.source_mode}`, 'meta'),
      E('p', 'Candidate plan only, not verified shootability. Staging is an uncalibrated screen-space rehearsal; geometric fit is unknown. Missing source fields are marked unknown.', 'unk'));
    for (const [i, s] of snapshot.scenes.entries()) {
      const sec = E('section', null, 'scene'), a = s.evidence?.frame;
      sec.append(E('h2', `${i + 1}. ${s.heading}`), E('p', s.description || '(no description)'));
      if (a) {
        const sh = s.staging;
        if (s.manual_frame) sec.append(E('p', 'Manual frame choice within assigned property; plan score refers to original solver selection.', 'meta'));
        try {
          const url = await dataUrl(`/image/${encodeURIComponent(a.shot_id)}`), im = await loadImg(url), cv = document.createElement('canvas');
          cv.width = 1280; cv.height = 720;
          drawStage(cv.getContext('2d'), 1280, 720, { imgEl: im, prov: s.provenance_label, shot: sh, t: null, editing: true, sel: -1 });
          const staged = E('img'), raw = E('img');
          staged.src = cv.toDataURL('image/jpeg', 0.88); staged.alt = `Staged rehearsal frame, scene ${i + 1}`;
          raw.src = url; raw.alt = `Indexed source frame ${a.shot_id}`;
          sec.append(E('h4', 'Staged frame (uncalibrated screen space)'), staged, E('h4', 'Indexed source frame'), raw);
        } catch (e) { sec.append(E('p', `Indexed image unavailable: ${e.message}`, 'unk')); }
        sec.append(E('h4', `Variant ${snapshot.variant} · ${sh.duration_sec}s`), E('p', sh.dialogue || '(no dialogue)'));
        sh.actors.forEach((ac) => sec.append(E('p', `${ac.name} (${ac.pose}, scale ${ac.scale}): (${ac.x0.toFixed(2)}, ${ac.y0.toFixed(2)}) → (${ac.x1.toFixed(2)}, ${ac.y1.toFixed(2)})`, 'meta')));
      }
      sec.append(doc.importNode(evidenceNodes(s.id, s.evidence), true)); doc.body.append(sec);
    }
    download(new Blob([`<!doctype html>\n${doc.documentElement.outerHTML}`], { type: 'text/html' }), 'typecast-shootpack.html');
    status('Shoot pack downloaded. Open it and use Print to save a PDF.');
  } catch (e) { status(`Shoot pack export failed: ${e.message}`, true); } finally { $('expPack').disabled = !plan(); }
}

// ---------- movie preview reel (logic lives in director-reel.js; this is only the hook) ----------
let reelCtrl = null;
function reelInput() {
  return { variant: S.variant, scenes: S.scenes.filter((s) => assignFor(s.id)).map((s) => ({ id: s.id, heading: s.heading,
    shot_id: assignFor(s.id).shot_id, prov: provText(s.id), shot: sanitizeShot(shotData(s.id)) })) };
}
async function exportReel() {
  if (reelCtrl) return;
  if (!window.TypecastReel) return status('Reel module failed to load; no reel was produced.', true);
  let snap;
  try { snap = TypecastReel.buildSnapshot(reelInput()); } catch (e) { return status(`Reel not recorded: ${e.message}`, true); }
  stopPlay(); reelCtrl = new AbortController(); $('expReel').disabled = true; $('cancelReel').hidden = false;
  let last = '';
  const say = (msg) => { if (msg !== last) { last = msg; status(msg); } };
  try {
    const out = await TypecastReel.recordReel(snap, { render: drawStage, signal: reelCtrl.signal,
      loadImage: async (id) => loadImg(await dataUrl(`/image/${encodeURIComponent(id)}`)),
      onProgress: (p) => say(p.phase === 'loading' ? `Reel: loading indexed frames (${p.done}/${p.total})…`
        : p.phase === 'recording' ? `Reel: recording scene ${p.scene} of ${snap.scenes.length} in real time (${snap.total_sec}s). Keep this tab visible.`
        : 'Reel: finalizing…') });
    download(out.blob, `typecast-reel-variant-${snap.variant}.webm`);
    status(`Reel downloaded: ${out.scenes} scene(s), ${out.duration_sec}s, ${(out.bytes / 1e6).toFixed(1)} MB silent ${out.mimeType}. Uncalibrated 2D rehearsal; geometric fit unknown.`);
  } catch (e) {
    status(e.code === 'cancelled' ? 'Reel cancelled; nothing was saved.' : `Reel not recorded: ${e.message}`, e.code !== 'cancelled');
  } finally { reelCtrl = null; $('cancelReel').hidden = true; $('expReel').disabled = !plan(); }
}

// ---------- saved projects ----------
function renderProjectReview() {
  const box = $('projectReview'); box.replaceChildren(); box.hidden = !S.importReview.length;
  if (!S.importReview.length) return;
  box.append(el('p', { text: 'Saved staging needs review. It was not applied to replacement frames. Project JSON exports retain these drafts.' }));
  for (const draft of S.importReview) box.append(el('p', { class: 'meta', text:
    `${draft.scene_id}: saved frame ${draft.frame.shot_id}, property ${draft.frame.property_id}. Both variants retained.` }));
}
const constraints = () => ({ max_locations: Math.floor(clamp($('maxLoc').value, 1, 4, 3)), require_available: $('reqAvail').checked,
  trucks: Math.floor(clamp($('trucks').value, 0, 20, 0)), cars: Math.floor(clamp($('cars').value, 0, 50, 0)) });
async function importProject(file) {
  $('impProject').value = '';
  if (!file) return;
  if (S.planBusy) return status('Wait for the current plan or project import to finish.', true);
  // Claim the operation and snapshot the user's state before the first await, so nothing
  // typed during a slow file read or evidence request can be overwritten.
  busy(true);
  const rev = S.rev, scriptAtStart = $('script').value, limits = constraints();
  try {
    if (file.size > TypecastProject.MAX_BYTES) throw new Error('Project file exceeds 1 MB.');
    const project = TypecastProject.normalizeProject(await file.text());
    stopPlay(); cancelGen(); clearPending();
    status('Rebuilding project evidence using the current visible location and vehicle constraints…');
    const scenes = project.scenes.map(({ id, heading, description }) => ({ id, heading, description }));
    const data = await api('/api/production/plan', { scenes, forbidden_property_ids: [], ...limits });
    // Newer user work must never be silently overwritten by a slow import.
    if (S.rev !== rev || $('script').value !== scriptAtStart)
      throw new Error('you changed the script or staging while the project was loading, so nothing was replaced. Import again when ready');
    if (JSON.stringify(constraints()) !== JSON.stringify(limits))
      throw new Error('location or vehicle constraints changed while evidence was loading, so the result would not match the visible controls. Import again');
    const restored = TypecastProject.restoreEdits(project, data);
    // Commit only after validation and retrieval succeed. Imported evidence never becomes source truth.
    Object.assign(S, { scenes, resp: data, planIdx: 0, sceneId: scenes[0].id, actorIdx: 0,
      edits: restored.edits, frameOverrides: restored.frameOverrides, importReview: restored.reviewNeeded,
      frameChange: {}, forbidden: [], undo: null, variant: project.variant });
    $('undo').disabled = true;
    $('script').value = scenes.map((scene) => `${scene.heading} | ${scene.description}`.replace(/[\r\n]+/g, ' ')).join('\n');
    $('varA').setAttribute('aria-pressed', String(S.variant === 'A'));
    $('varB').setAttribute('aria-pressed', String(S.variant === 'B'));
    renderAll();
    status(`Project loaded with fresh evidence. ${restored.restored} scene draft(s) restored to exact saved frames; ${restored.reviewNeeded.length} retained for review.`, !!restored.reviewNeeded.length);
  } catch (e) { status(`Project not loaded; existing work kept: ${e.message}`, true); }
  finally { busy(false); }
}
$('impProject').addEventListener('change', (event) => importProject(event.target.files[0]));

// ---------- events ----------
$('build').addEventListener('click', () => build(false));
$('script').addEventListener('input', () => { S.rev++; });
$('demo').addEventListener('click', () => { S.rev++; $('script').value = DEMO; status('Demo script loaded. Press Build plan to fetch real results.'); });
$('planSel').addEventListener('change', (e) => {
  const prev = assignMap(); stopPlay(); cancelGen(); clearPending();
  S.planIdx = clamp(e.target.value, 0, (S.resp?.plans.length || 1) - 1, 0); noteFrameChanges(prev); renderAll();
});
$('clearRej').addEventListener('click', () => { S.forbidden = []; renderPlan(); status('Rejections cleared. Build plan again to apply.'); });
$('reject').addEventListener('click', reject);
let scanViewfinder;
$('lookAround').addEventListener('click', async () => {
  const assignment = assignFor(S.sceneId);
  if (!assignment || S.planBusy) return;
  try {
    const { Viewfinder } = await import('/app/viewfinder.js');
    if (!scanViewfinder) {
      scanViewfinder = new Viewfinder();
      scanViewfinder.dialog.addEventListener('close', () => $('lookAround').focus());
    }
    const source = new Image();
    source.src = `/image/${encodeURIComponent(assignment.shot_id)}`;
    source.alt = S.scenes.find(s => s.id === S.sceneId)?.heading || 'Indexed room';
    await source.decode();
    await scanViewfinder.open(assignment.shot_id, source);
  } catch (error) { status('Scan view unavailable. The indexed rehearsal frame is still available.', true); }
});
$('varA').addEventListener('click', () => setVariant('A'));
$('varB').addEventListener('click', () => setVariant('B'));
$('play').addEventListener('click', play);
$('pause').addEventListener('click', pause);
$('reset').addEventListener('click', () => { stopPlay(); draw(); status('Reset.'); });
$('dur').addEventListener('change', (e) => { const sh = shotData(S.sceneId); if (!sh) return; sh.duration_sec = clamp(e.target.value, 1, 30, 5); e.target.value = sh.duration_sec; edited(); });
$('dur').addEventListener('input', (e) => {
  const sh = shotData(S.sceneId), value = Number(e.target.value);
  if (sh && e.target.value !== '' && Number.isFinite(value) && value >= 1 && value <= 30) {
    sh.duration_sec = value; edited();
  }
});
$('dlg').addEventListener('input', (e) => { const sh = shotData(S.sceneId); if (!sh) return; sh.dialogue = e.target.value.slice(0, 800); edited(); });
$('actorSel').addEventListener('change', (e) => { stopPlay(); S.actorIdx = Number(e.target.value) || 0; syncActor(curActor()); draw(); });
$('addActor').addEventListener('click', () => {
  const sh = shotData(S.sceneId); if (!sh || sh.actors.length >= 3) return;
  const n = sh.actors.length, x = r3(0.3 + 0.2 * n);
  sh.actors.push({ id: `a${Date.now().toString(36)}${n}`, name: `Actor ${n + 1}`, pose: 'stand', x0: x, y0: 0.85, x1: x, y1: 0.85, scale: 1 });
  S.actorIdx = n; renderInspector(); edited();
});
$('delActor').addEventListener('click', () => { const sh = shotData(S.sceneId); if (!sh || !curActor()) return; sh.actors.splice(S.actorIdx, 1); S.actorIdx = 0; renderInspector(); edited(); });
$('aName').addEventListener('input', (e) => { const a = curActor(); if (!a) return; a.name = e.target.value.slice(0, 24) || 'Actor'; $('actorSel').options[S.actorIdx].textContent = a.name; edited(); });
$('aPose').addEventListener('change', (e) => { const a = curActor(); if (!a) return; a.pose = POSES.includes(e.target.value) ? e.target.value : 'stand'; edited(); });
$('aScale').addEventListener('input', (e) => { const a = curActor(); if (!a) return; a.scale = clamp(e.target.value, 0.3, 2, a.scale); edited(); });
for (const f of ['x0', 'y0', 'x1', 'y1']) $(`a${f}`).addEventListener('input', (e) => { const a = curActor(); if (!a) return; a[f] = r3(clamp(e.target.value, 0, 1, a[f])); edited(); });
const cv = $('stage'); let drag = null;
const norm = (e) => { const r = cv.getBoundingClientRect(); return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height }; };
function hit(p, sh) {
  const sel = sh.actors[S.actorIdx];
  if (sel && Math.hypot((p.x - sel.x1) * 16 / 9, p.y - sel.y1) < 0.04) return { i: S.actorIdx, end: true };
  for (let i = sh.actors.length - 1; i >= 0; i--) {
    const a = sh.actors[i];
    if (Math.abs(p.x - a.x0) < 0.03 * a.scale + 0.012 && p.y <= a.y0 + 0.03 && p.y >= a.y0 - a.scale * 0.34) return { i, end: false };
  }
  return null;
}
cv.addEventListener('pointerdown', (e) => {
  const sh = shotData(S.sceneId); if (!sh) return;
  if (S.play.on || S.play.acc) stopPlay();
  const h = hit(norm(e), sh); if (!h) return draw();
  const a = sh.actors[h.i]; drag = { ...h, key: keyOf(S.sceneId), variant: S.variant, pointerId: e.pointerId, link: !h.end && a.x1 === a.x0 && a.y1 === a.y0 };
  S.actorIdx = h.i; cv.setPointerCapture(e.pointerId); renderInspector(); draw();
});
cv.addEventListener('pointermove', (e) => {
  if (!drag) return;
  if (drag.key !== keyOf(S.sceneId) || drag.variant !== S.variant || drag.pointerId !== e.pointerId) return endDrag();
  const a = shotData(S.sceneId)?.actors[drag.i]; if (!a) { drag = null; return; }
  const p = norm(e), x = r3(clamp(p.x, 0, 1, 0)), y = r3(clamp(p.y, 0, 1, 0));
  S.rev++; invalidateProposal();
  if (drag.end) { a.x1 = x; a.y1 = y; } else { a.x0 = x; a.y0 = y; if (drag.link) { a.x1 = x; a.y1 = y; } }
  syncActor(a); draw();
});
const endDrag = () => { if (drag) { const id = drag.pointerId; drag = null; if (cv.hasPointerCapture(id)) cv.releasePointerCapture(id); renderTimeline(); } };
cv.addEventListener('pointerup', endDrag); cv.addEventListener('pointercancel', endDrag);
cv.addEventListener('lostpointercapture', endDrag);
cv.addEventListener('keydown', (e) => {
  const a = curActor(), d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
  if (!a || !d) return;
  e.preventDefault(); const [fx, fy] = e.shiftKey ? ['x1', 'y1'] : ['x0', 'y0'], step = e.altKey ? 0.05 : 0.01;
  a[fx] = r3(clamp(a[fx] + d[0] * step, 0, 1, a[fx])); a[fy] = r3(clamp(a[fy] + d[1] * step, 0, 1, a[fy]));
  syncActor(a); edited();
});
$('gen').addEventListener('click', generate);
$('applyB').addEventListener('click', applyB);
$('discard').addEventListener('click', () => { clearPending(); status('Proposal discarded. Nothing changed.'); });
$('undo').addEventListener('click', undoApply);
$('expPng').addEventListener('click', () => {
  stopPlay(); draw();
  try { cv.toBlob((b) => (b ? download(b, `typecast-${S.sceneId || 'stage'}-${S.variant}.png`) : status('PNG export failed.', true)), 'image/png'); }
  catch (e) { status(`PNG export failed: ${e.message}`, true); }
});
$('expJson').addEventListener('click', () => {
  const proj = exportSnapshot();
  download(new Blob([JSON.stringify(proj, null, 2)], { type: 'application/json' }), 'typecast-project.json');
  status('Project JSON downloaded.');
});
$('expPack').addEventListener('click', exportPack);
$('expReel').addEventListener('click', exportReel);
$('cancelReel').addEventListener('click', () => reelCtrl && reelCtrl.abort());
window.addEventListener('pagehide', () => { if (rec) rec.stop(); if (reelCtrl) reelCtrl.abort(); stopPlay(); });

$('script').value = DEMO;
renderAll();
status('Edit the script, then Build plan. Nothing appears on the stage until the backend returns real results.');
