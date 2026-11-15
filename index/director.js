'use strict';
const $ = (id) => document.getElementById(id);
const POSES = ['stand', 'sit', 'walk'];
const ORIGIN_SAMPLE = 'authored-sample', ORIGIN_TAG = 'AUTHORED SAMPLE · not AI';
const PLANNING_REQUESTS = new WeakMap();
const BADGE = 'UNCALIBRATED SCREEN-SPACE REHEARSAL · GEOMETRIC FIT UNKNOWN';
// Stage palette and type follow the scouting app (web/styles.css tokens).
const INK = { bg: '#0b0d0d', text: '#f2efe8', muted: '#adb5b3', accent: '#edbd69', scrim: 'rgba(11,13,13,.74)' };
const FACE = 'Barlow, "Segoe UI", system-ui, sans-serif', SLUG = '"Barlow Condensed", Barlow, system-ui, sans-serif';
// Visually checked against live indexed frames: three rooms in one Houston building.
const DEMO = [
  'INT. HOUSTON APARTMENT KITCHEN - DAY | A bright Houston apartment kitchen with cabinets, an island and a counter; two sisters prepare coffee.',
  'INT. HOUSTON APARTMENT LIVING ROOM - DAY | A furnished Houston apartment living room with a sofa and broad windows; a visitor waits.',
  'INT. HOUSTON APARTMENT BEDROOM - DAY | A Houston apartment bedroom with a bed and daylight from a window; a woman packs a suitcase.',
].join('\n');
const S = { mode: 'film', save: null, saveTx: null, decisions: Object.create(null), builtScript: '', comm: Object.create(null), brief: { reviewer: '', date: '', notes: '' }, swaps: Object.create(null), transfer: Object.create(null), alt: Object.create(null), swapUndo: null, notes: Object.create(null), built: null, compare: false, rev: 0, scenes: [], resp: null, planIdx: 0, planBusy: false, sceneId: null, variant: 'A', forbidden: [], edits: {},
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
// The solver returns similarity-first alternatives. Recommend maximum coverage,
// then fewer company moves; keep the higher-similarity alternatives selectable.
function orderPlans(data) {
  data.plans.sort((a, b) => (a.uncovered_scene_ids || []).length - (b.uncovered_scene_ids || []).length
    || a.locations - b.locations || (b.mean_similarity ?? -Infinity) - (a.mean_similarity ?? -Infinity));
}
function planSummary(p) {
  const covered = S.scenes.length - (p.uncovered_scene_ids || []).length;
  const noun = T('scenes', 'needs'), base = `${covered}/${S.scenes.length} ${noun} · ${p.locations} location${p.locations === 1 ? '' : 's'} · ${p.company_moves ?? '?'} move${p.company_moves === 1 ? '' : 's'}`;
  return p === plan() && anySwap() ? `${covered}/${S.scenes.length} ${noun} · location swapped by hand, totals not recalculated` : base;
}

// ---------- data access ----------
const plan = () => (S.resp && S.resp.plans[S.planIdx]) || null;
// A swap is honoured only while its frame is still an eligible candidate for that scene and its property is not rejected.
function validSwap(sid) {
  const sw = S.swaps[`${S.planIdx}::${sid}`];
  if (!sw) return null;
  const c = candFor(sid, sw.shot_id);
  return c && c.eligible !== false && c.shot.property_id === sw.property_id && !S.forbidden.includes(sw.property_id) ? sw : null;
}
const assignFor = (sid) => {
  const a = (plan()?.assignments || []).find((x) => x.scene_id === sid);
  if (!a) return null;
  const sw = validSwap(sid);
  if (sw) return { ...a, shot_id: sw.shot_id, property_id: sw.property_id, manual_frame: true, swapped: true };
  const chosen = S.frameOverrides[`${S.planIdx}::${sid}`];
  return chosen ? { ...a, shot_id: chosen, manual_frame: true } : a;
};
// A swap chosen by Save the scene that equals the revised plan's own assignment does not make the plan totals stale.
const swapStale = (s) => { const sw = validSwap(s.id); if (!sw) return false; if (sw.via !== 'save') return true; const a = (plan()?.assignments || []).find((x) => x.scene_id === s.id); return !a || a.shot_id !== sw.shot_id || a.property_id !== sw.property_id; };
const anySwap = () => S.scenes.some(swapStale);
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
const assignMap = () => Object.fromEntries((plan()?.assignments || []).map((a) => [a.scene_id, assignFor(a.scene_id)?.shot_id ?? a.shot_id]));
function noteFrameChanges(prev) {
  for (const [sid, old] of Object.entries(prev)) {
    const a = assignFor(sid);
    if (a && a.shot_id !== old && hasWork(S.edits[`${sid}::${old}`]) && !hasWork(S.edits[`${sid}::${a.shot_id}`]))
      S.frameChange[sid] = { from: old, to: a.shot_id };
  }
}
// `origin` is provenance, never content: model responses and unknown values cannot set it; only trusted callers pass keepOrigin.
function sanitizeShot(s, keepOrigin = false) {
  const actors = (Array.isArray(s?.actors) ? s.actors : []).slice(0, 3).map((a, i) => {
    const x0 = r3(clamp(a?.x0, 0, 1, 0.5)), y0 = r3(clamp(a?.y0, 0, 1, 0.85));
    return { id: String(a?.id ?? `a${i + 1}`).slice(0, 32), name: String(a?.name ?? '').slice(0, 24) || `Actor ${i + 1}`,
      pose: POSES.includes(a?.pose) ? a.pose : 'stand', x0, y0,
      x1: r3(clamp(a?.x1, 0, 1, x0)), y1: r3(clamp(a?.y1, 0, 1, y0)), scale: clamp(a?.scale, 0.3, 2, 1) };
  });
  const out = { duration_sec: clamp(s?.duration_sec, 1, 30, 5), dialogue: String(s?.dialogue ?? '').slice(0, 800), actors };
  if (keepOrigin && s?.origin === ORIGIN_SAMPLE) out.origin = ORIGIN_SAMPLE;
  if (keepOrigin && s?.carried === true) out.carried = true;
  return out;
}

// ---------- backend ----------
function parseScenes() {
  const r = TypecastChecks.parseScript($('script').value, S.mode);
  if (r.error) throw new Error(r.error);
  return r.scenes.map(({ id, heading, description }) => ({ id, heading, description }));
}
// A reviewable reading of the pasted text, shown before Build: what became a scene, what was cut or ignored.
function renderParse() {
  const box = $('parseSummary'); if (!box) return;
  box.replaceChildren();
  const r = TypecastChecks.parseScript($('script').value, S.mode), noun = S.mode === 'community' ? 'need' : 'scene';
  if (r.error) { box.append(el('p', { class: 'warn', text: r.error })); return; }
  const list = el('ol', { class: 'parse-list' }, ...r.scenes.map((sc) => el('li', {}, el('b', { text: sc.heading }),
    el('span', { class: 'meta', text: ` · ${sc.description.length} characters${sc.dialogue_lines ? ` · ${sc.dialogue_lines} dialogue line${sc.dialogue_lines === 1 ? '' : 's'} kept in the text` : ''}${sc.truncated ? ' · cut to fit' : ''}` }))));
  const d = el('details', { class: 'parse-details' }, el('summary', { text: `Reads as ${r.scenes.length} ${noun}${r.scenes.length === 1 ? '' : 's'}${r.notes.length ? ` · ${r.notes.length} note${r.notes.length === 1 ? '' : 's'}` : ''}` }), list,
    ...r.notes.map((n) => el('p', { class: 'warn', text: n })));
  box.append(d);
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
  for (const b of $('framePicker').querySelectorAll('button')) b.disabled = on;   // strips rendered mid-build must not stay disabled
  $('gen').disabled = on || !!S.gen.ctrl;
  if ($('saveBtn')) $('saveBtn').disabled = on || S.mode !== 'film' || !S.sceneId || !assignFor(S.sceneId);
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
const MOCK_NOTE = 'MOCK FIXTURE RESULTS: placeholder frames, fixture rankings and fixture statuses, not real rooms, sources or capacity. ';
const modeNote = (data) => (data?.mode === 'mock' ? MOCK_NOTE : '');
async function build(reuse) {
  if (S.planBusy) return;
  const planningError = S.mode === 'film' && window.TypecastPlanning?.validate();
  if (planningError) return status(planningError, true);
  stopPlay(); cancelGen(); clearPending(); if (S.save) closeSave();
  let scenes;
  try { scenes = reuse ? S.scenes : parseScenes(); } catch (e) { return status(e.message, true); }
  const body = { scenes, max_locations: clamp($('maxLoc').value, 1, 4, 3), forbidden_property_ids: [...S.forbidden],
    require_available: $('reqAvail').checked, trucks: Math.floor(clamp($('trucks').value, 0, 20, 0)),
    cars: Math.floor(clamp($('cars').value, 0, 50, 0)), ...planningConstraints() };
  const prev = assignMap();
  // What this request was built from. If any of it changes while the answer is in flight, the answer is for older inputs.
  const sig = () => JSON.stringify([reuse ? null : $('script').value, constraints(), [...S.forbidden]]);
  const sent = sig(), scriptSent = $('script').value;
  busy(true); status('Requesting production plan from backend…');
  try {
    const data = await api('/api/production/plan', body);
    if (!Array.isArray(data.scenes) || !Array.isArray(data.plans)) throw new Error('Malformed plan response');
    if (sig() !== sent) return status('That plan was built for your earlier script, constraints or rejections, which changed while it loaded. Nothing was replaced and your work is kept. Press Build plan again.', true);
    applyForbidden(data);
    PLANNING_REQUESTS.set(data, JSON.stringify(constraints()));
    orderPlans(data);
    S.scenes = scenes; S.resp = data; S.planIdx = 0; S.frameOverrides = {}; S.builtScript = reuse ? S.builtScript : scriptSent; S.swaps = Object.create(null); S.swapUndo = null; S.built = { trucks: body.trucks, cars: body.cars, require_available: body.require_available };
    if (!scenes.some((s) => s.id === S.sceneId)) { S.sceneId = scenes[0].id; S.actorIdx = 0; }
    noteFrameChanges(prev); renderAll();
    if (data.plans.length) status(`${modeNote(data)}${data.plans.length} candidate plan(s) returned. ${T('Candidates are not verified shootability.', 'Candidates are not verified, approved or available sites.')}`, data.mode === 'mock');
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
  if (S.save) closeSave();
  const a = assignFor(S.sceneId);
  if (!a) return status('This scene has no assigned location to reject.', true);
  if (!S.forbidden.includes(a.property_id)) S.forbidden.push(a.property_id);
  renderAll();   // a hand-swapped rejected location must vanish immediately, not after the replan returns
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
// The take as drawn/exported: flagged when its staging was carried to this frame and not yet reviewed there.
function viewShot(sid, v = S.variant) {
  const sh = shotData(sid, v), t = S.transfer[keyOf(sid)];
  return sh && t && !t.reviewed ? { ...sh, carried: true } : sh;
}
function provText(sid, v = S.variant) {
  const i = S.scenes.findIndex((s) => s.id === sid), a = assignFor(sid), c = a && candFor(sid, a.shot_id);
  if (S.mode === 'community') return `Need ${i + 1} · Matterport · property ${a ? safeId(a.property_id).slice(0, 12) : 'none'}`;
  return `Scene ${i + 1} · Variant ${v} · Matterport · property ${a ? safeId(a.property_id).slice(0, 12) : 'none'}`;
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
  ctx.strokeStyle = ctx.fillStyle = sel ? INK.accent : INK.text;
  ctx.shadowColor = 'rgba(0,0,0,.85)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 1; ctx.beginPath();
  if (a.pose === 'sit') { ctx.moveTo(px, hip); ctx.lineTo(px + 1.7 * u, hip); ctx.lineTo(px + 1.7 * u, py); } else {
    const sw = a.pose === 'walk' ? (t == null ? 0.9 : Math.sin(t * 7) * 1.1) * u : 0.45 * u;
    ctx.moveTo(px - sw, py); ctx.lineTo(px, hip); ctx.lineTo(px + sw, py);
  }
  ctx.moveTo(px, hip); ctx.lineTo(px, neck);
  const arm = a.pose === 'walk' && t != null ? Math.sin(t * 7 + Math.PI) * u : 0;
  ctx.moveTo(px - 1.2 * u + arm, hip - u); ctx.lineTo(px, neck + 0.4 * u); ctx.lineTo(px + 1.2 * u - arm, hip - u);
  ctx.moveTo(px + 0.8 * u, neck - 0.8 * u); ctx.arc(px, neck - 0.8 * u, 0.8 * u, 0, Math.PI * 2);
  ctx.stroke(); ctx.shadowBlur = 4; ctx.textAlign = 'center';
  ctx.font = `600 ${Math.max(15, u * 1.15)}px ${FACE}`; ctx.fillText(a.name, px, neck - 2 * u, 260);
  ctx.restore();
}
function pill(ctx, x, y, w, h) {
  ctx.beginPath();
  if (ctx.roundRect) ctx.roundRect(x, y, w, h, 5); else ctx.rect(x, y, w, h);
  ctx.fill();
}
// Camera frame marks around the real frame: the same language as the 360° viewfinder.
function frameMarks(ctx, x, y, w, h, alpha) {
  const k = Math.min(w, h) * 0.06;
  ctx.save(); ctx.strokeStyle = INK.accent; ctx.globalAlpha = alpha; ctx.lineWidth = 2; ctx.beginPath();
  for (const [cx, cy, dx, dy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
    ctx.moveTo(cx, cy + dy * k); ctx.lineTo(cx, cy); ctx.lineTo(cx + dx * k, cy);
  }
  ctx.stroke(); ctx.restore();
}
function drawStage(ctx, W, H, o) {
  ctx.save(); ctx.fillStyle = INK.bg; ctx.fillRect(0, 0, W, H);
  let marks;
  if (o.imgEl) {
    const iw = o.imgEl.naturalWidth || o.imgEl.width, ih = o.imgEl.naturalHeight || o.imgEl.height, s = Math.min(W / iw, H / ih);
    const dw = iw * s, dh = ih * s, dx = (W - dw) / 2, dy = (H - dh) / 2;
    if (dw < W - 1 || dh < H - 1) {
      // Fill the letterbox with a dimmed, blurred cover of the same frame; the real frame stays uncropped on top.
      const c = Math.max(W / iw, H / ih);
      ctx.save(); ctx.filter = 'blur(28px) saturate(.7)'; ctx.globalAlpha = 0.5;
      ctx.drawImage(o.imgEl, (W - iw * c) / 2, (H - ih * c) / 2, iw * c, ih * c); ctx.restore();
      ctx.fillStyle = 'rgba(11,13,13,.45)'; ctx.fillRect(0, 0, W, H);
    }
    ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 30; ctx.shadowOffsetY = 6;
    ctx.drawImage(o.imgEl, dx, dy, dw, dh); ctx.restore();
    marks = [dx + 12, dy + 12, dw - 24, dh - 24, 0.7];
  } else {
    marks = [W * 0.08, H * 0.1, W * 0.84, H * 0.8, 0.35];
    ctx.fillStyle = INK.text; ctx.globalAlpha = 0.86; ctx.font = `600 34px ${FACE}`; ctx.textAlign = 'center';
    ctx.fillText(o.missing || 'No frame', W / 2, H / 2 + 10, W - 160); ctx.globalAlpha = 1;
  }
  const sh = o.shot;
  if (sh) sh.actors.forEach((a, i) => {
    const k = o.t == null ? 0 : clamp(o.t / sh.duration_sec, 0, 1, 0), moved = a.x1 !== a.x0 || a.y1 !== a.y0;
    if (o.editing && (moved || i === o.sel)) {
      const on = i === o.sel;
      ctx.save(); ctx.strokeStyle = on ? INK.accent : 'rgba(242,239,232,.7)'; ctx.lineWidth = 3; ctx.setLineDash([10, 8]);
      ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 4; ctx.shadowOffsetY = 1; ctx.beginPath();
      ctx.moveTo(a.x0 * W, a.y0 * H); ctx.lineTo(a.x1 * W, a.y1 * H); ctx.stroke(); ctx.setLineDash([]);
      ctx.beginPath(); ctx.arc(a.x1 * W, a.y1 * H, 13, 0, Math.PI * 2); ctx.stroke(); ctx.restore();
    }
    figure(ctx, H, (a.x0 + (a.x1 - a.x0) * k) * W, (a.y0 + (a.y1 - a.y0) * k) * H, a, o.t, o.editing && i === o.sel);
  });
  frameMarks(ctx, ...marks);
  // Honesty label and provenance travel with every still and reel frame.
  ctx.textBaseline = 'middle'; ctx.textAlign = 'left'; ctx.font = `600 21px ${FACE}`;
  const badge = o.badge || BADGE, bw = Math.min(ctx.measureText(badge).width, W * 0.56) + 28;
  ctx.fillStyle = INK.scrim; pill(ctx, 18, 18, bw, 40);
  ctx.fillStyle = INK.accent; ctx.fillText(badge, 32, 38.5, W * 0.56);
  if (sh && sh.origin) {
    ctx.textAlign = 'left'; ctx.font = `600 19px ${FACE}`;
    const tw = Math.min(ctx.measureText(ORIGIN_TAG).width, W * 0.5) + 28;
    ctx.fillStyle = INK.scrim; pill(ctx, 18, 66, tw, 36); ctx.fillStyle = INK.text; ctx.fillText(ORIGIN_TAG, 32, 84.5, W * 0.5);
  }
  if (sh && sh.carried) {
    ctx.textAlign = 'left'; ctx.font = `600 19px ${FACE}`;
    const label = 'STAGING CARRIED OVER · UNREVIEWED ON THIS FRAME', cw = Math.min(ctx.measureText(label).width, W * 0.62) + 28, cy = sh.origin ? 108 : 66;
    ctx.fillStyle = INK.scrim; pill(ctx, 18, cy, cw, 36); ctx.fillStyle = INK.accent; ctx.fillText(label, 32, cy + 18.5, W * 0.62);
  }
  ctx.textAlign = 'right'; ctx.font = `500 19px ${FACE}`;
  const pw = Math.min(ctx.measureText(o.prov).width, W * 0.36) + 28;
  ctx.fillStyle = INK.scrim; pill(ctx, W - 18 - pw, 18, pw, 40);
  ctx.fillStyle = INK.text; ctx.fillText(o.prov, W - 32, 38.5, W * 0.36);
  ctx.textBaseline = 'alphabetic';
  if (sh && sh.dialogue) {
    // Subtitles, as on a cut: two lines at most over a soft scrim.
    ctx.font = `500 30px ${FACE}`; const lines = wrap(ctx, sh.dialogue, W - 220), bh = 40 + lines.length * 40;
    const g = ctx.createLinearGradient(0, H - bh - 40, 0, H);
    if (g && g.addColorStop) { g.addColorStop(0, 'rgba(11,13,13,0)'); g.addColorStop(1, 'rgba(11,13,13,.82)'); ctx.fillStyle = g; }
    else ctx.fillStyle = INK.scrim;
    ctx.fillRect(0, H - bh - 40, W, bh + 40);
    ctx.fillStyle = INK.text; ctx.textAlign = 'center'; ctx.shadowColor = 'rgba(0,0,0,.9)'; ctx.shadowBlur = 6; ctx.shadowOffsetY = 2;
    lines.forEach((l, i) => ctx.fillText(l, W / 2, H - bh + 34 + i * 40, W - 160));
  }
  ctx.restore();
}
function liveArgs(sid, t, v = S.variant, editing = t == null, sel = S.actorIdx) {
  const a = assignFor(sid), im = a ? img(a.shot_id) : null;
  const missing = !S.resp ? 'Build a plan to load real indexed frames' : !a ? 'Uncovered scene: no location assigned'
    : im.err ? `Indexed image unavailable (${a.shot_id})` : 'Loading indexed frame…';
  return { imgEl: im && im.ok ? im.el : null, missing, prov: provText(sid, v), shot: a && S.mode === 'film' ? viewShot(sid, v) : null, badge: S.mode === 'community' ? COMM_BADGE : undefined, t, editing, sel };
}
// Read-only A/B preview of the SAME selected/playing frame: two natively sized panes (no stretching), one real-time clock.
// A take shorter than the clock holds its last pose and says so; durations are never normalized.
function drawCompare(ctx, W, H, sid, t) {
  const pw = W / 2, ph = H / 2, py = (H - ph) / 2;
  ctx.save(); ctx.fillStyle = INK.bg; ctx.fillRect(0, 0, W, H);
  ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
  for (const [idx, v] of [[0, 'A'], [1, 'B']]) {
    const sh = shotData(sid, v), x = idx * pw, dur = sh ? sh.duration_sec : null;
    const tv = t == null || dur == null ? t : Math.min(t, dur);
    ctx.save(); ctx.beginPath(); ctx.rect(x, py, pw, ph); ctx.clip(); ctx.translate(x, py);
    drawStage(ctx, pw, ph, liveArgs(sid, tv, v, t == null, -1)); ctx.restore();
    const ended = t != null && dur != null && t > dur;
    const clock = dur == null ? 'no frame' : t == null ? `${dur}s` : ended ? `ended at ${dur}s, holding last pose` : `${t.toFixed(1)}s / ${dur}s`;
    ctx.font = `600 26px ${FACE}`; ctx.fillStyle = S.variant === v ? INK.accent : INK.text;
    ctx.fillText(`TAKE ${v}${S.variant === v ? ' (active take)' : ''}${sh?.origin ? ' · authored sample' : ''}`, x + 14, py - 62, pw - 28);
    ctx.font = `500 22px ${FACE}`; ctx.fillStyle = INK.muted; ctx.fillText(clock, x + 14, py - 28, pw - 28);
  }
  ctx.fillStyle = INK.accent; ctx.fillRect(pw - 1, py, 2, ph);
  ctx.font = `500 21px ${FACE}`; ctx.fillStyle = INK.muted; ctx.textAlign = 'center';
  ctx.fillText('Comparison view only. Not an export. Same indexed frame; uncalibrated screen-space staging.', W / 2, py + ph + 44, W - 40);
  ctx.restore();
}
function drawSingle(t = null, sid = S.sceneId) { const c = $('stage'); drawStage(c.getContext('2d'), c.width, c.height, liveArgs(sid, t)); }
function draw(t = null, sid = S.sceneId) {
  const c = $('stage');
  if (S.compare) drawCompare(c.getContext('2d'), c.width, c.height, sid, t); else drawSingle(t, sid);
}

// ---------- playback ----------
function play() {
  if (S.play.on) return;
  const q = S.scenes.filter((s) => assignFor(s.id)).map((s) => ({ sid: s.id,
    dur: S.compare ? Math.max(shotData(s.id, 'A').duration_sec, shotData(s.id, 'B').duration_sec) : shotData(s.id).duration_sec }));
  if (!q.length) return status('Nothing to play: no scene has an assigned frame.', true);
  const total = q.reduce((n, x) => n + x.dur, 0);
  if (S.play.acc >= total) S.play.acc = 0;
  Object.assign(S.play, { on: true, q, total, start: performance.now() });
  status(S.compare ? 'Playing both takes side by side on one real-time clock; a shorter take holds its last pose.' : `Playing variant ${S.variant}.`);
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
function highlight(sid) {
  for (const b of $('timeline').querySelectorAll('button')) b.classList.toggle('now', b.dataset.sid === sid);
  // The header names whatever the stage shows: the playing scene during playback, else the selected one.
  if ((sid || S.sceneId) !== headSid) renderStageHead(sid || S.sceneId);
}

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
const T = (film, community) => (S.mode === 'community' ? community : film);
function warningMeaning(w) {
  if (w.field === 'property_id/model_id') return w.status === 'matched'
    ? 'Exact CoStar property-to-Matterport model match. This property identity groups scenes into fewer locations.'
    : w.status === 'conflict' ? 'IDs conflict with the supplied mapping; excluded from candidate plans.'
    : 'Property-to-model association could not be confirmed from the supplied mapping.';
  if (w.field === 'parking_capacity') return w.status === 'insufficient'
    ? 'Estimated capacity is below the requested vehicles; excluded from candidate plans.'
    : w.status === 'estimated' ? 'Capacity is estimated; verify before the shoot.' : 'Parking capacity is unknown; this is not a parking approval.';
  if (w.field === 'geometry') return T('Room geometry is incomplete or estimated. Rehearsal positions do not establish physical clearance.', 'Room geometry is incomplete or estimated. It does not establish clearance, exits or capacity.');
  if (w.field === 'property') return T('Property details are unavailable. Listing availability and filming permission are not established.', 'Property details are unavailable. Listing availability and permission to use the site are not established.');
  return 'Review this source field before production.';
}
// A plain-language brief built only from the sanitized summary; unknowns stay unknown.
function evidenceBrief(a) {
  const ul = el('ul', { class: 'brief' });
  const item = (k, v, unknown = false) => ul.append(el('li', {}, el('b', { text: k }), el('span', { class: unknown ? 'unk' : '', text: v })));
  const num = (v, d = 0) => (typeof v === 'number' ? v.toFixed(d) : null);
  const p = a.property || {}, lg = a.logistics || {}, r = a.room || {};
  const av = p.availability_status;
  item('Listing', av === 'available' ? T('Marketed as available. Not filming permission.', 'Marketed as available. Not permission to use the site.')
    : av === 'not_available' ? 'Not marketed as available.' : 'Unknown.', av !== 'available' && av !== 'not_available');
  const building = [num(p.year_built) && `built ${num(p.year_built)}`, num(p.size_sqft) && `${Number(p.size_sqft).toLocaleString('en-US')} sq ft`].filter(Boolean);
  item('Building', building.length ? building.join(' · ') : 'Unknown.', !building.length);
  const room = [num(r.room_area_m2) && `${num(r.room_area_m2)} m² floor`, num(r.ceiling_m, 1) && `ceiling ${num(r.ceiling_m, 1)} m`,
    num(r.depth_m, 1) && `depth ${num(r.depth_m, 1)} m`].filter(Boolean);
  item('Room', room.length ? `${room.join(' · ')} (index estimate, not a capacity)` : 'Unknown. Measure on site.', !room.length);
  if (lg.parking_status === 'unknown') item('Parking', 'Unknown. Not a parking approval.', true);
  else item('Parking', `${num(lg.truck_spaces) ?? '?'} trucks, ${num(lg.car_spaces) ?? '?'} cars, ${lg.parking_status}`
    + (lg.enough_parking === true ? '. Covers the requested vehicles.' : lg.enough_parking === false ? '. Short of the requested vehicles.' : '.'));
  item(T('Crew walk', 'Walk from parking'), lg.walk_status === 'unknown' ? 'Unknown.' : `${num(lg.walk_m) ?? '?'} m, ${lg.walk_status}.`, lg.walk_status === 'unknown');
  item('Noise', lg.noise_status === 'unknown' ? 'Unknown.' : `Proximity screen, ${lg.noise_status}. Not a sound measurement.`, lg.noise_status === 'unknown');
  return ul;
}
function evidenceNodes(sid, summary = evidenceSummary(sid), collapsible = true) {
  const f = document.createDocumentFragment(), a = summary;
  if (!a) { f.append(el('p', { class: 'unk', text: S.resp ? 'Uncovered in this plan: no location assigned.' : 'No plan yet.' })); return f; }
  const fields = [kv('Frame · Matterport index', a.frame),
    kv(T('Room metrics · index estimate, not calibrated to stage', 'Room metrics · index estimate, not a measurement or a capacity'), a.room),
    kv('Property · CoStar', a.property), kv('Logistics · Vexcel', a.logistics)];
  const w = el('section', { class: 'ev' }, el('h4', { text: 'Source warnings' })), ws = a.warnings;
  if (!ws.length) w.append(el('p', { class: 'meta', text: 'No warnings returned. Absence of a warning is not verification.' }));
  ws.forEach((x) => w.append(el('p', { class: 'warn', text: `[${x.source}] ${x.field} · ${x.status}: ${warningMeaning(x)}` })));
  if (!collapsible) { f.append(...fields, w); return f; }
  f.append(evidenceBrief(a), w,
    el('details', { class: 'ev-details' }, el('summary', { text: 'Exact source fields' }), ...fields));
  return f;
}
function renderPlan() {
  const sel = $('planSel'), plans = S.resp?.plans || []; sel.replaceChildren();
  plans.forEach((p, i) => {
    sel.append(el('option', { value: String(i), text: planSummary(p), title: `Mean similarity ${fmt(p.mean_similarity)}` }));
  });
  sel.value = String(S.planIdx); sel.disabled = S.planBusy || !plans.length;
  sel.title = plan() ? `${planSummary(plan())} · mean similarity ${fmt(plan().mean_similarity)}` : '';
  $('planMeta').textContent = S.resp ? `${S.resp.mode === 'mock' ? 'MOCK FIXTURES · ' : ''}Best coverage, then fewest locations. Selected similarity ${fmt(plan()?.mean_similarity)}. Mode ${S.resp.mode ?? 'unknown'} · ${count(S.resp.evaluated_subsets)} subsets evaluated · pool ${count(S.resp.pool_properties)} properties. Similarity is visual retrieval, not shootability.` : 'No plan yet.';
  $('forbidden').textContent = S.forbidden.length ? `Rejected: ${S.forbidden.join(', ')}` : 'No rejected locations.';
  $('clearRej').disabled = !S.forbidden.length;
  window.TypecastPlanning?.render();
}
function sceneButton(s, i, cls, ...kids) {
  const b = el('button', { type: 'button', 'data-sid': s.id }, ...kids);
  if (s.id === S.sceneId) b.setAttribute('aria-current', 'true');
  b.addEventListener('click', () => selectScene(s.id));
  return el('li', { class: cls }, b);
}
// Real indexed frames as thumbnails; identifiers stay in the evidence panel.
// One element per list and frame, reused across re-renders so edits never re-decode or flash.
const THUMBS = new Map();
function thumb(shotId, where) {
  const key = `${where}:${shotId}`;
  let i = THUMBS.get(key);
  if (!i) {
    i = el('img', { class: 'thumb', alt: '', decoding: 'async' });
    i.src = `/image/${encodeURIComponent(shotId)}`;
    THUMBS.set(key, i);
  }
  return i;
}
const noThumb = () => el('span', { class: 'thumb', 'aria-hidden': 'true' });
// Plans group scenes by property; a letter per location shows which scenes share a company move.
function locLetter(pid) {
  const order = [];
  for (const s of S.scenes) { const a = assignFor(s.id); if (a && !order.includes(a.property_id)) order.push(a.property_id); }
  const i = order.indexOf(pid);
  return i < 0 ? '?' : String.fromCharCode(65 + (i % 26));
}
function renderRail() {
  $('rail').replaceChildren(...S.scenes.map((s, i) => { const a = assignFor(s.id);
    return sceneButton(s, i, '', a ? thumb(a.shot_id, 'rail') : noThumb(), el('strong', { class: 'slug', text: `${i + 1}. ${s.heading}` }),
      el('small', { text: s.description || '(no description)' }),
      el('span', { class: a ? 'loc' : 'loc none', text: a ? `Location ${locLetter(a.property_id)}${a.swapped ? ' · swapped' : a.manual_frame ? ' · your frame' : ''}${S.mode === 'film' && (continuityMap()[s.id] || []).some((c) => c.level !== 'unknown') ? ' · continuity note' : ''}` : S.resp ? 'Uncovered: no location' : 'Not planned yet' })); }));
}
function renderTimeline() {
  $('timeline').replaceChildren(...S.scenes.map((s, i) => { const a = assignFor(s.id), sh = a ? shotData(s.id) : null;
    const n = sh ? sh.actors.length : 0;
    return sceneButton(s, i, '', a ? thumb(a.shot_id, 'cut') : noThumb(), el('strong', { text: `${i + 1} · ${sh ? `${sh.duration_sec}s` : 'skipped'}` }), el('span', { text: s.heading }),
      el('small', { text: sh ? `${n ? `${n} stand-in${n > 1 ? 's' : ''}` : 'No stand-ins'} · take ${S.variant}${sh.origin ? ' · authored sample' : ''}` : 'no frame; not played' })); }));
}
function stageLocNodes(sid = S.sceneId) {
  const a = assignFor(sid);
  if (!S.resp) return [document.createTextNode('Build a plan to put real indexed rooms on the stage.')];
  if (!a) return [document.createTextNode('Uncovered in this plan: no location assigned.')];
  const shared = S.scenes.map((s, i) => [s, i + 1]).filter(([s]) => s.id !== sid && assignFor(s.id)?.property_id === a.property_id).map(([, n]) => n);
  const parts = [`CoStar property ${safeId(a.property_id)}`];
  if (shared.length) parts.push(`same location as scene${shared.length > 1 ? 's' : ''} ${shared.join(', ')}`);
  if (a.manual_frame) parts.push('your frame choice');
  return [el('strong', { text: `Location ${locLetter(a.property_id)}` }), document.createTextNode(` · ${parts.join(' · ')}`)];
}
let headSid = null;
function renderStageHead(sid = S.sceneId) {
  headSid = sid;
  const title = $('stageTitle'), where = $('stageLoc'), mode = $('planMode');
  const summary = $('stagePlanSummary');
  if (summary) { summary.textContent = plan() ? planSummary(plan()) : ''; summary.hidden = !plan(); }
  if (title) title.textContent = S.scenes.find((s) => s.id === sid)?.heading || 'Stage';
  if (where) where.replaceChildren(...stageLocNodes(sid));
  if (mode) {
    const m = S.resp ? String(S.resp.mode ?? 'unknown').slice(0, 12) : null;
    mode.dataset.mode = !m ? 'none' : ['live', 'mock', 'mixed'].includes(m) ? m : 'unknown';
    mode.textContent = m ? `${m.toUpperCase()} DATA` : 'NO PLAN';
  }
}
function syncActor(a) {
  $('aName').value = a ? a.name : ''; $('aPose').value = a ? a.pose : 'stand'; $('aScale').value = a ? a.scale : '';
  for (const f of ['x0', 'y0', 'x1', 'y1']) $(`a${f}`).value = a ? a[f].toFixed(2) : '';
}
function renderInspector() {
  const shot = shotData(S.sceneId); $('varLbl').textContent = S.variant; $('shotForm').disabled = !shot || S.compare;
  $('dur').value = shot ? shot.duration_sec : ''; $('dlg').value = shot ? shot.dialogue : '';
  if (shot && S.actorIdx >= shot.actors.length) S.actorIdx = Math.max(0, shot.actors.length - 1);
  const sel = $('actorSel'); sel.replaceChildren(...(shot?.actors || []).map((a, i) => el('option', { value: String(i), text: a.name })));
  sel.value = String(S.actorIdx); const a = shot?.actors[S.actorIdx];
  $('actorForm').disabled = !a || S.compare; $('addActor').disabled = !shot || S.compare || shot.actors.length >= 3; $('delActor').disabled = !a || S.compare;
  syncActor(a);
  const tag = $('originTag'); tag.hidden = !shot?.origin;
  tag.textContent = shot?.origin ? `${ORIGIN_TAG}: take ${S.variant} derives from pre-written sample blocking (not AI-generated). Edits you make keep this origin.` : '';
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
  const label = el('label', { text: `${T('Frames in this location (creative choice)', 'Frames in this site')} · ${choices.length}` }), select = el('select', { 'aria-label': 'Frame within assigned property' });
  const sim = (v) => (typeof v === 'number' ? v.toFixed(2) : 'unknown');
  choices.forEach((c, n) => select.append(el('option', { value: c.shot.shot_id, text: `Frame ${n + 1} · similarity ${sim(c.shot.score)}` })));
  select.value = a.shot_id;
  select.disabled = S.planBusy;
  select.addEventListener('change', () => {
    const prev = assignMap(); S.rev++; stopPlay(); cancelGen(); clearPending();
    const k0 = `${S.planIdx}::${S.sceneId}`;
    if (validSwap(S.sceneId)) S.swaps[k0] = { ...S.swaps[k0], shot_id: select.value }; else S.frameOverrides[k0] = select.value;
    noteFrameChanges(prev); renderAll(); status('Manual frame selected within the same property. Plan score still describes the original solver selection.');
  });
  label.append(select); box.append(label);
  if (choices.length > 1) {
    const strip = el('div', { class: 'frame-strip', role: 'group', 'aria-label': 'Frames in this location' });
    choices.slice(0, 12).forEach((c, n) => {
      const b = el('button', { type: 'button', 'aria-pressed': String(c.shot.shot_id === a.shot_id), 'aria-label': `Use frame ${n + 1}` },
        thumb(c.shot.shot_id, 'frames'), el('span', { text: `${n + 1} · ${sim(c.shot.score)}` }));
      b.disabled = S.planBusy;
      b.addEventListener('click', () => {
        if (select.value === c.shot.shot_id) return;
        select.value = c.shot.shot_id; select.dispatchEvent(new Event('change'));
      });
      strip.append(b);
    });
    box.append(strip);
  }
  box.append(altLocations(a));
  if (a.manual_frame) box.append(el('p', { class: 'meta', text: 'Manual frame choice. Plan similarity describes the original solver selection; property budget is unchanged.' }));
}
// ---------- try another location (swap), checks, continuity ----------
const sceneNumber = (sid) => S.scenes.findIndex((s) => s.id === sid) + 1;
function altChoices(sid) {
  const a = assignFor(sid), sc = S.resp?.scenes?.find((s) => s.id === sid), seen = new Set(a ? [a.property_id] : []), out = [];
  for (const c of sc?.candidates || []) {
    if (c.eligible === false || !c.shot || seen.has(c.shot.property_id) || S.forbidden.includes(c.shot.property_id)) continue;
    seen.add(c.shot.property_id); out.push(c);
    if (out.length >= 6) break;
  }
  return out;
}
function altLocations(a) {
  const sid = S.sceneId, choices = altChoices(sid);
  const box = el('details', { class: 'alt-locs' }, el('summary', { text: `${T('Try another location', 'Try another site')} (${choices.length})` }));
  if (!choices.length) { box.append(el('p', { class: 'meta', text: 'No other eligible location is in this plan\'s candidate pool. Reject or change constraints, then rebuild, to widen it.' })); return box; }
  if (S.mode === 'community') box.append(el('p', { class: 'meta', text: 'One click switches this need to that candidate site. Checks and notes you recorded stay with each site. To rule a site out everywhere, use Rule out site. Nothing here approves a site.' }));
  else box.append(el('p', { class: 'meta', text: 'One click swaps this scene only, and carries your staging over as a draft to review. To remove a property from every plan, use Reject location instead. The plan summary is not recalculated.' }));
  const strip = el('div', { class: 'frame-strip', role: 'group', 'aria-label': 'Other candidate locations' });
  for (const c of choices) {
    const sim = typeof c.shot.score === 'number' ? c.shot.score.toFixed(2) : 'unknown';
    const b = el('button', { type: 'button', 'aria-label': `Swap scene ${sceneNumber(sid)} to property ${safeId(c.shot.property_id)}, similarity ${sim}` },
      thumb(c.shot.shot_id, 'alt'), el('span', { text: `${safeId(c.shot.property_id).slice(0, 14)} · ${sim}` }));
    b.disabled = S.planBusy;
    b.addEventListener('click', () => swapLocation(sid, c.shot.shot_id));
    strip.append(b);
  }
  box.append(strip);
  return box;
}
function swapLocation(sid, shotId) {
  if (S.planBusy) return status('Wait for the new plan before swapping a location.', true);
  const cur = assignFor(sid), c = candFor(sid, shotId);
  if (!cur || !c || c.eligible === false || S.forbidden.includes(c.shot.property_id) || c.shot.property_id === cur.property_id) return status('Pick a different location here; frames in the current location use the frame picker.', true);
  const k = `${S.planIdx}::${sid}`, oldKey = keyOf(sid), newKey = `${sid}::${shotId}`;
  S.swapUndo = { sid, k, prevSwap: S.swaps[k] ? { ...S.swaps[k] } : null, prevOverride: S.frameOverrides[k] ?? null };
  S.rev++; stopPlay(); cancelGen(); clearPending(); delete S.frameChange[sid];
  S.swaps[k] = { shot_id: shotId, property_id: c.shot.property_id, from_shot_id: cur.shot_id, from_property_id: cur.property_id };
  delete S.frameOverrides[k];
  if (!S.edits[newKey] && S.edits[oldKey] && hasWork(S.edits[oldKey])) {
    S.edits[newKey] = clone(S.edits[oldKey]);
    S.transfer[newKey] = { from_shot_id: cur.shot_id, from_property_id: cur.property_id, reviewed: false };
  } else if (hasWork(S.edits[newKey]) && S.edits[oldKey] && hasWork(S.edits[oldKey]) && JSON.stringify(S.edits[newKey]) !== JSON.stringify(S.edits[oldKey])) {
    S.swaps[k].dest_kept = true;   // this frame already holds different staging; it is kept and offered, never overwritten
  }
  renderAll();
  status(`Scene ${sceneNumber(sid)} now uses ${safeId(c.shot.property_id)}. Your staging came along as a draft: review it on this frame.`);
}
// The destination frame already had staging: it was kept. These two actions are the only ways to change that, and neither deletes anything.
function useCurrentTakesHere() {
  const sid = S.sceneId, sw = validSwap(sid), newKey = keyOf(sid), fromKey = sw && `${sid}::${sw.from_shot_id}`;
  if (!sw || !S.edits[fromKey] || !S.edits[newKey]) return;
  S.rev++; stopPlay(); cancelGen(); clearPending();
  S.alt[newKey] = { edits: clone(S.edits[newKey]), transfer: S.transfer[newKey] ? { ...S.transfer[newKey] } : null };
  S.edits[newKey] = clone(S.edits[fromKey]);
  S.transfer[newKey] = { from_shot_id: sw.from_shot_id, from_property_id: sw.from_property_id, reviewed: false };
  sw.dest_kept = false; renderAll();
  status('Your current takes now replace the earlier staging on this frame as an unreviewed draft. The earlier staging is kept: use "Switch to the other saved staging".');
}
function switchStaging() {
  const newKey = keyOf(S.sceneId), other = S.alt[newKey];
  if (!other || !S.edits[newKey]) return;
  S.rev++; stopPlay(); cancelGen(); clearPending();
  const mine = { edits: S.edits[newKey], transfer: S.transfer[newKey] ? { ...S.transfer[newKey] } : null };
  S.edits[newKey] = other.edits;
  if (other.transfer) S.transfer[newKey] = other.transfer; else delete S.transfer[newKey];
  S.alt[newKey] = mine; renderAll();
  status('Switched to the other saved staging on this frame. Nothing was deleted; both versions stay in this session.');
}
function undoSwap() {
  const u = S.swapUndo; if (!u) return;
  S.rev++; stopPlay(); cancelGen(); clearPending();
  if (u.prevSwap) S.swaps[u.k] = u.prevSwap; else delete S.swaps[u.k];
  if (u.prevOverride) S.frameOverrides[u.k] = u.prevOverride; else delete S.frameOverrides[u.k];
  S.swapUndo = null; renderAll(); status('Swap undone. Staging made on the other frame is kept there, not deleted.');
}
function backToPlanned() {
  const k = `${S.planIdx}::${S.sceneId}`; if (!S.swaps[k]) return;
  S.rev++; stopPlay(); cancelGen(); clearPending(); delete S.swaps[k]; S.swapUndo = null; renderAll();
  status('Back to the planned location. Staging made on the swapped frame is kept there, not deleted.');
}
function renderSwapNotice() {
  const n = $('swapNotice'), sid = S.sceneId, sw = validSwap(sid), t = S.transfer[keyOf(sid)] ;
  n.replaceChildren();
  const unrev0 = !!(t && !t.reviewed) && S.mode === 'film';
  if (!sw && !unrev0) { n.hidden = true; return; }
  const eff = sw || { from_property_id: t.from_property_id, property_id: assignFor(sid)?.property_id, from_shot_id: t.from_shot_id };
  const unreviewed = unrev0;
  const row = el('div', { class: 'row' });
  if (unreviewed) {
    const ok = el('button', { type: 'button', class: 'primary', text: 'Staging looks right on this frame' });
    ok.addEventListener('click', () => { S.rev++; t.reviewed = true; renderAll(); status('Marked reviewed by eye on this exact frame. That is artistic alignment, not a survey: room fit remains unverified.'); });
    row.append(ok);
  }
  if (S.saveTx && S.saveTx.sid === sid && S.saveTx.rev === S.rev) { const u = el('button', { type: 'button', text: 'Undo Save the scene' }); u.addEventListener('click', undoSave); row.append(u); }
  if (S.swapUndo && S.swapUndo.sid === sid) { const u = el('button', { type: 'button', text: 'Undo swap' }); u.addEventListener('click', undoSwap); row.append(u); }
  if (sw && sw.dest_kept) { const use = el('button', { type: 'button', text: 'Use my current takes here instead' }); use.addEventListener('click', useCurrentTakesHere); row.append(use); }
  if (S.alt[keyOf(sid)]) { const sw2 = el('button', { type: 'button', text: 'Switch to the other saved staging' }); sw2.addEventListener('click', switchStaging); row.append(sw2); }
  if (sw && sw.via !== 'save') { const back = el('button', { type: 'button', text: 'Back to planned location' }); back.addEventListener('click', backToPlanned); row.append(back); }
  // The main sentence depends on what actually happened to the takes on this frame.
  const main = S.mode === 'community' ? 'This need now points at another candidate site. Your coordinator checks stay with each site, so re-check this one. Nothing here approves a site.' : sw && sw.dest_kept ? 'This frame already had its own staging, so it was kept; your current takes were not copied. Room fit remains unverified.'
    : unreviewed ? 'Takes copied to this frame for review. Review stand-in placement; room fit remains unverified.'
    : 'The plan summary and company moves were not recalculated for this choice. Reviewing by eye is artistic alignment, not a survey: room fit remains unverified.';
  n.append(el('p', { text: `Location ${eff.via === 'save' ? 'changed by Save the scene' : 'swapped'} for scene ${sceneNumber(sid)}: ${safeId(eff.from_property_id)} → ${safeId(eff.property_id)}. ${main}` }),
    el('p', { class: 'meta', text: T('The earlier scan identity does not apply to this frame. Stand-ins are uncalibrated screen space, and source warnings and provenance labels stay as shown.', 'The earlier site identity does not apply to this frame. Source warnings and provenance labels stay as shown.') }),
    ...(S.alt[keyOf(sid)] ? [el('p', { class: 'meta', text: 'A second saved staging exists for this frame. It lives in this session only; the project file saves the one shown.' })] : []), row);
  n.hidden = false;
}
const sceneGroup = (sid) => (S.notes[sid]?.group || '');
function continuityMap() {
  const list = S.scenes.map((s, i) => { const a = assignFor(s.id), sh = a ? shotData(s.id) : null;
    return { id: s.id, number: i + 1, heading: s.heading, group: sceneGroup(s.id),
      frame: a ? { shot_id: a.shot_id, property_id: a.property_id } : null, take: sh ? { actors: sh.actors } : null }; });
  return window.TypecastChecks ? TypecastChecks.continuity(list, S.variant) : {};
}
function fitFor(sid) {
  const a = assignFor(sid), s = S.scenes.find((x) => x.id === sid);
  if (!window.TypecastChecks || !s) return null;
  return TypecastChecks.fitCheck({ scene: s, cand: a ? candFor(sid, a.shot_id) : null, built: S.built, mode: S.resp?.mode, domain: S.mode });
}
function checkRow(r) {
  return el('li', { class: `chk chk-${r.kind}` }, el('b', { text: `${TypecastChecks.KIND_LABEL[r.kind] || 'Note'}: ` }), el('span', { text: `${r.label}. ${r.detail}` }),
    r.source ? el('small', { text: ` Source: ${r.source}.` }) : '');
}
function renderChecks() {
  const box = $('sceneChecks'), sid = S.sceneId, a = assignFor(sid);
  if (!window.TypecastChecks || !a) { box.hidden = true; return; }
  const fit = fitFor(sid), cont = S.mode === 'film' ? (continuityMap()[sid] || []) : [], real = cont.filter((c) => c.level !== 'unknown');
  const body = $('checksBody'); body.replaceChildren();
  $('checksSummary').textContent = `${S.mode === 'community' ? 'Site fit evidence' : 'Fit check'} · ${TypecastChecks.fitSummaryText(fit)}${real.length ? ` · ${real.length} continuity note${real.length === 1 ? '' : 's'}` : ''}`;
  body.append(el('p', { class: 'meta', text: `Only fields the sources supplied are compared. Unknown stays unknown, and image similarity is not a fit score. Only simple wording in your ${S.mode === 'community' ? 'needs' : 'script'} (at least / no more than / more than / less than with m², ft² or a ceiling height) is read; other needs are not extracted.` }),
    el('ul', { class: 'chk-list' }, ...fit.rows.map(checkRow)));
  const hist = S.mode === 'film' ? decisionHistoryNodes(sid) : null; if (hist) body.append(hist);
  if (cont.length) {
    body.append(el('h4', { text: 'Continuity (from your link)' }), el('ul', { class: 'chk-list' }, ...cont.map((c) => el('li', { class: `chk chk-${c.level === 'verified' ? 'conflict' : c.level === 'potential' ? 'unknown' : 'info'}` },
      el('b', { text: `${c.level === 'verified' ? 'Mismatch' : c.level === 'potential' ? 'Possible mismatch' : 'Cannot compare'}: ` }), el('span', { text: c.text }), el('small', { text: ` Next: ${c.action}` })))));
  }
  box.hidden = false;
}
function renderNotes() {
  const sid = S.sceneId, n = S.notes[sid] || {};
  $('noteDressing').value = n.dressing || ''; $('noteGroup').value = n.group || '';
  $('prodNotes').hidden = !sid;
}
const cleanText = (v, max) => String(v || '').replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, '').slice(0, max);
function setNote(field, value) {
  const sid = S.sceneId; if (!sid) return;
  const n = (S.notes[sid] ||= { dressing: '', group: '' });
  n[field] = field === 'group' ? cleanText(value, 12).replace(/[^A-Za-z0-9_-]/g, '') : cleanText(value, 600);
  if (!n.dressing && !n.group) delete S.notes[sid];
  S.rev++; renderChecks(); renderRail();
}
function renderCompareStrip() {
  const strip = $('compareStrip'), btn = $('cmpAB'), on = S.compare;
  btn.setAttribute('aria-pressed', String(on));
  $('stage').classList.toggle('comparing', on);
  strip.hidden = !on; strip.replaceChildren();
  if (!on) return;
  const a = shotData(S.sceneId, 'A'), b = shotData(S.sceneId, 'B');
  const durs = a && b ? `Take A runs ${a.duration_sec}s, take B ${b.duration_sec}s${a.duration_sec === b.duration_sec ? '' : ' (different lengths: scene playback lasts the longer one and the shorter take holds its last pose)'}.`
    : 'This scene has no assigned frame to compare.';
  const cap = (v, sh) => el('span', { class: 'cap' }, el('strong', { text: `Take ${v}${S.variant === v ? ' (active)' : ''}` }),
    ` · ${sh ? `${sh.duration_sec}s` : 'no frame'}${sh?.origin ? ` · ${ORIGIN_TAG}` : ''}`);
  strip.append(el('div', { class: 'caps' }, cap('A', a), cap('B', b)));
  strip.append(el('span', {}, el('strong', { text: 'Read-only A/B comparison' }), ` · same frame, one real-time clock. ${durs}`),
    el('span', { text: `Canvas drag/keys and take fields are locked while comparing. Active take ${S.variant}: PNG and WebM export that take only; Project JSON and Shoot pack include both. Uncalibrated screen-space staging.` }));
}
function toggleCompare() {
  stopPlay(); S.compare = !S.compare; renderAll();
  status(S.compare ? `Comparing take A and take B (read-only). Active take stays ${S.variant}.` : `Back to single-take view (take ${S.variant}).`);
}
function renderAll() {
  renderProjectReview();
  renderPlan(); renderRail(); renderTimeline(); renderInspector(); renderFrameNotice(); renderFrames(); renderStageHead(); renderCompareStrip(); renderSwapNotice(); renderChecks(); renderNotes(); renderSite(); renderSavePanel(); refreshSaveStale();
  $('evidence').replaceChildren(evidenceNodes(S.sceneId));
  const a = assignFor(S.sceneId), pl = $('planner');
  $('lookAround').disabled = S.planBusy || !a;
  $('reject').disabled = S.planBusy || !a; $('expPack').disabled = !plan(); $('expReel').disabled = !plan() || !!reelCtrl; pl.hidden = !a;
  if (a) pl.href = `/api/plan/${encodeURIComponent(a.shot_id)}?heading=0&focal=35`;
  if ($('plannerOut')) { $('plannerOut').hidden = true; $('plannerOut').replaceChildren(); }
  draw();
}
function invalidateProposal() {
  if (S.gen.ctrl || S.pending) { cancelGen(); clearPending(); status('Staging changed; generate a new proposal to review.'); }
}
function edited() { S.rev++; invalidateProposal(); stopPlay(); draw(); renderTimeline(); }
function selectScene(sid) {
  stopPlay(); cancelGen();
  if (S.pending) { clearPending(); status('Pending proposal discarded because the scene changed.'); }
  if (S.save) closeSave();
  S.sceneId = sid; S.actorIdx = 0; renderAll();
}
function setVariant(v) {
  stopPlay(); cancelGen(); clearPending(); S.variant = v; S.compare = false;
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
    const r = await api('/api/production/brainstorm', { instruction: instruction.slice(0, 2000), heading: sc.heading, description: sc.description, shot: clone(shot) }, ctrl.signal);
    if (tok !== S.gen.tok || keyOf(S.sceneId) !== k) return;
    if (!r.shot || typeof r.shot !== 'object') throw new Error('model returned no shot');
    S.pending = { k, shot: sanitizeShot(r.shot), creativeNote: String(r.creative_note ?? '').slice(0, 600) };
    $('pSum').textContent = String(r.summary ?? '(no summary)').slice(0, 400);
    $('pNote').textContent = String(r.creative_note ?? '').slice(0, 600);
    $('pDiff').replaceChildren(...diffLines(S.edits[k].B, S.pending.shot).map((t) => el('li', { text: t })));
    $('proposal').hidden = false; status('Proposal ready. Nothing has changed yet; review, then Apply to B or Discard.');
  } catch (e) {
    if (e.name === 'AbortError' || tok !== S.gen.tok) return;
    status(`Brainstorm unavailable: ${e.message}. No changes made.`, true);
  } finally { if (tok === S.gen.tok) { S.gen.ctrl = null; setGen(false); } }
}
// Explicit opt-in, offline: a fixed authored blocking pattern. It makes no model call, ignores the direction text and
// is staged through the same review step, so nothing changes until Apply to B. Take A is only read.
const SAMPLE_NOTE = 'Pre-authored sample blocking, not AI-generated: it ignores your direction text and no model was called. It mirrors the stand-ins of take A left-to-right and gives any that stand still a short authored cross toward centre; a generic performer is used if take A is empty. It says nothing about real geometry or the source frame.';
function loadSample() {
  if (S.planBusy) return status('Wait for the new plan before loading a sample.', true);
  const sid = S.sceneId, a = shotData(sid, 'A'), b = shotData(sid, 'B');
  if (!a || !b) return status('Select a scene with an assigned frame first.', true);
  cancelGen(); clearPending();               // aborts any in-flight model request; its late reply is dropped by token
  const k = keyOf(sid), src = sanitizeShot(a);
  const actors = src.actors.length ? src.actors.map((p) => {
    const x0 = r3(1 - p.x0), moved = p.x1 !== p.x0 || p.y1 !== p.y0;
    const x1 = moved ? r3(1 - p.x1) : r3(clamp(x0 + (x0 < 0.5 ? 0.2 : -0.2), 0.05, 0.95, x0));
    return { ...p, x0, x1, y1: moved ? p.y1 : p.y0, pose: moved || p.pose !== 'stand' ? p.pose : 'walk' };
  }) : [{ id: 'sample1', name: 'Performer', pose: 'walk', x0: 0.25, y0: 0.85, x1: 0.7, y1: 0.85, scale: 1 }];
  S.pending = { k, sample: true, shot: { ...sanitizeShot({ duration_sec: src.duration_sec, dialogue: src.dialogue, actors }), origin: ORIGIN_SAMPLE } };
  $('pSum').textContent = 'Authored sample alternative (pre-written, not AI-generated)';
  $('pNote').textContent = SAMPLE_NOTE;
  $('pDiff').replaceChildren(...diffLines(b, S.pending.shot).map((t) => el('li', { text: t })));
  $('proposal').hidden = false;
  status('Authored sample loaded for review (not AI, no model call). Nothing has changed yet: Apply to B or Discard.');
}
function applyB() {
  if (!S.pending || keyOf(S.sceneId) !== S.pending.k) { clearPending(); return status('Proposal no longer matches this scene; discarded.', true); }
  const sample = !!S.pending.sample;
  S.rev++; const ed = S.edits[S.pending.k]; S.undo = { k: S.pending.k, prev: clone(ed.B), sid: S.sceneId, notes: clone(S.notes[S.sceneId] || null) }; ed.B = clone(S.pending.shot);
  if (!sample && S.pending.creativeNote) {
    const n = S.notes[S.sceneId] ||= { dressing: '', group: '' };
    n.dressing = `${n.dressing ? n.dressing + '\n' : ''}AI creative suggestion (unrendered set changes): ${S.pending.creativeNote}`.slice(0, 600);
  }
  S.undo.appliedNotes = clone(S.notes[S.sceneId] || null);
  clearPending(); $('undo').disabled = false; stopPlay(); renderAll();
  status(`${sample ? 'Applied the authored sample to variant B' : 'Applied to variant B'}${S.variant === 'B' || S.compare ? '.' : '. Switch to B to view it.'}`);
}
function undoApply() {
  if (!S.undo || !S.edits[S.undo.k]) return;
  S.rev++;
  if (S.undo.sid && JSON.stringify(S.notes[S.undo.sid] || null) === JSON.stringify(S.undo.appliedNotes)) {
    if (S.undo.notes) S.notes[S.undo.sid] = S.undo.notes;
    else delete S.notes[S.undo.sid];
  }
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
const PACK_PRINT = '@media print{body{max-width:none;margin:0;font-size:11pt}section.scene{break-inside:avoid-page;page-break-inside:avoid}img{max-height:9cm;width:auto;max-width:100%}.sheet li{list-style:none}.sheet li:before{content:"\\2610 "}h1,h2,h3{break-after:avoid}}.sheet{border:1px solid #c98a1c;padding:.6rem .9rem;margin:.8rem 0;background:#fbf6ec}.sheet h3{margin:.2rem 0 .4rem}.sheet ul{padding-left:1.1rem}.sheet .k{font-weight:bold}.sheet p,.sheet li{max-width:72ch}.sheet li{margin:.25rem 0}.takes{display:flex;gap:.6rem;flex-wrap:wrap}.takes figure{margin:0;flex:1 1 280px}.takes img{width:100%}';
const PACK_CSS = 'body{font:14px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a120c}section.scene{break-inside:avoid;border-top:2px solid #c98a1c;padding:1rem 0}img{width:100%;border:1px solid #ccc}.meta{color:#6b5847;font-size:12px}dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:12px}dt{color:#6b5847}dd{margin:0}.unk{color:#b3261e;font-style:italic}.warn{font-size:12px}h4{margin:.6rem 0 .2rem}' + PACK_PRINT;
// Safe, validated per-scene production state that Project JSON carries (identifiers and bounded text only).
function sceneProduction(sid) {
  const out = {}, sw = validSwap(sid), t = S.transfer[keyOf(sid)], n = S.notes[sid];
  if (sw) out.location_choice = { shot_id: safeId(sw.shot_id), property_id: safeId(sw.property_id), from_shot_id: safeId(sw.from_shot_id), from_property_id: safeId(sw.from_property_id), staging_reviewed: !(t && !t.reviewed) };
  if (n && (n.dressing || n.group)) out.notes = { dressing: cleanText(n.dressing, 600), group: cleanText(n.group, 12) };
  if (S.mode === 'film' && S.decisions[sid]) out.decision = deep(S.decisions[sid]);
  return out;
}
function exportSnapshot() {
  const p = plan();
  return clone({ app: 'Typecast Director', exported_at: new Date().toISOString(), variant: S.variant, plan_index: S.planIdx,
    honesty: S.mode === 'community' ? 'Candidate-site planning notes only. Coordinator checks are reported by a person and are not verified. Nothing here approves a site or establishes capacity, safety or availability. Plan score describes original solver frames.' : 'Candidate plans only. Uncalibrated screen-space rehearsal; geometric fit unknown. Plan score describes original solver frames; manual frame choices retain the assigned property.',
    source_mode: S.resp?.mode ?? 'unknown', locations: anySwap() ? null : count(p?.locations), company_moves: anySwap() ? null : p?.company_moves ?? null, mean_similarity: anySwap() ? null : p?.mean_similarity ?? null,
    ...communityExport(),
    plan_note: anySwap() ? 'A location was swapped by hand; plan locations, moves and similarity were not recalculated.' : undefined,
    review_needed: S.importReview,
    scenes: S.scenes.map((s) => ({ ...s, ...sceneProduction(s.id), evidence: evidenceSummary(s.id),
      manual_frame: !!assignFor(s.id)?.manual_frame, staging: assignFor(s.id) && S.mode === 'film' ? sanitizeShot(shotData(s.id), true) : null,
      variants: assignFor(s.id) && S.mode === 'film' ? { A: sanitizeShot(shotData(s.id, 'A'), true), B: sanitizeShot(shotData(s.id, 'B'), true) } : null,
      provenance_label: provText(s.id) })) });
}
function decisionFor(sid) {
  const a = assignFor(sid); if (!a || !window.TypecastChecks) return null;
  const fit = fitFor(sid), cont = continuityMap()[sid] || [], sw = validSwap(sid), t = S.transfer[keyOf(sid)];
  const take = (v) => sanitizeShot(shotData(sid, v), true);
  return { number: sceneNumber(sid), property: safeId(a.property_id), shot: safeId(a.shot_id), swap: sw ? { from: safeId(sw.from_property_id) } : null,
    carried: !!(t && !t.reviewed), takes: { A: take('A'), B: take('B') }, fit, cont, notes: S.notes[sid] || null,
    saved: S.decisions[sid] || null, checklist: TypecastChecks.checklist(fit, cont, { carried: !!(t && !t.reviewed) }) };
}
function decisionNodes(E, d, activeVariant) {
  const box = E('div', null, 'sheet');
  box.append(E('h3', `Production decision sheet · scene ${d.number}`),
    E('p', 'This sheet records choices and open questions. It contains no prices, permissions, owner contact or confirmation that a set is feasible.', 'meta'));
  box.append(E('h4', 'Location choice'), E('p', `Property ${d.property}, frame ${d.shot}.${d.swap ? ` Chosen by hand from the candidate pool instead of ${d.swap.from}; plan totals were not recalculated.` : ' As selected by the plan or your frame choice.'}`));
  if (d.carried) box.append(E('p', 'Staging was carried over from another frame and has NOT been reviewed on this one. Positions are uncalibrated screen space.', 'unk'));
  box.append(E('h4', `Takes (both are shown above; take ${activeVariant} is the active take)`));
  for (const v of ['A', 'B']) {
    const t = d.takes[v];
    box.append(E('p', `Take ${v}: ${t.duration_sec}s, ${t.actors.length} stand-in${t.actors.length === 1 ? '' : 's'}${t.dialogue ? `, line: ${t.dialogue}` : ', no dialogue'}${t.origin ? ' · AUTHORED SAMPLE (pre-written, not AI-generated)' : ''}.`, 'meta'));
  }
  const ul = (items) => { const u = E('ul'); items.forEach((i) => u.append(E('li', i))); return u; };
  if (d.saved) {
    const r = d.saved, u0 = (items) => { const u = E('ul'); items.forEach((i) => u.append(E('li', i))); return u; };
    box.append(E('h4', 'Saved decision (historical record, not current source data)'),
      E('p', `Recorded ${r.decided_at.slice(0, 10)}. Requirement ${r.original.trucks} truck(s), ${r.original.cars} car(s)${r.original.require_available ? ', available listing' : ''} → ${r.revised.trucks} truck(s), ${r.revised.cars} car(s)${r.revised.require_available ? ', available listing' : ''}. Property ${r.before ? r.before.property_id : 'none'} (frame ${r.before ? r.before.shot_id : 'none'}) → ${r.after ? r.after.property_id : 'none'} (frame ${r.after ? r.after.shot_id : 'none'}). Scope: the whole plan was re-planned${r.moved_scenes ? `; ${r.moved_scenes} other scene(s) moved` : ''}. This is a planning comparison, not an approval, an agent trace or a feasibility statement.`),
      u0(r.differences), E('h4', 'Unresolved when decided'), u0(r.unresolved));
  }
  box.append(E('h4', 'Fit evidence (sources, not a score; only simple wording in your script is read)'), ul(d.fit.rows.map((r) => `${TypecastChecks.KIND_LABEL[r.kind]}: ${r.label}. ${r.detail}${r.source ? ` Source: ${r.source}.` : ''}`)));
  const real = d.cont;
  if (real.length) box.append(E('h4', 'Continuity (from your link)'), ul(real.map((c) => `${c.level === 'verified' ? 'Mismatch' : c.level === 'potential' ? 'Possible mismatch' : 'Cannot compare'}: ${c.text} Next: ${c.action}`)));
  box.append(E('h4', 'Dressing (your notes; Typecast suggests none here)'), E('p', d.notes && d.notes.dressing ? d.notes.dressing : '(none entered)', d.notes && d.notes.dressing ? '' : 'meta'));
  box.append(E('h4', 'On-site checklist'), ul(d.checklist));
  return box;
}
async function exportPack() {
  const p = plan(); if (!p) return status('Build a plan first.', true);
  const snapshot = exportSnapshot(), sheets = S.scenes.map((s) => decisionFor(s.id));
  stopPlay(); $('expPack').disabled = true; status('Building shoot pack from real indexed images…');
  try {
    const doc = document.implementation.createHTMLDocument('Typecast shoot pack');
    const E = (tag, text, cls) => { const n = doc.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
    const cs = doc.createElement('meta'); cs.setAttribute('charset', 'utf-8');
    const csp = doc.createElement('meta'); csp.setAttribute('http-equiv', 'Content-Security-Policy');
    csp.setAttribute('content', "default-src 'none'; img-src data:; style-src 'unsafe-inline'");
    const st = doc.createElement('style'); st.textContent = PACK_CSS; doc.head.prepend(cs, csp); doc.head.append(st);
    doc.body.append(E('h1', 'Typecast shoot pack'),
      E('p', `Generated ${snapshot.exported_at} · Variant ${snapshot.variant} · Plan ${snapshot.plan_index + 1}: ${snapshot.locations ?? 'unknown'} location(s), ${snapshot.company_moves ?? 'unknown'} company move(s), mean original-plan similarity ${fmt(snapshot.mean_similarity)} · mode ${snapshot.source_mode}`, 'meta'),
      E('p', 'Candidate plan only, not verified shootability. Staging is an uncalibrated screen-space rehearsal; geometric fit is unknown. Missing source fields are marked unknown.', 'unk'));
    for (const [i, s] of snapshot.scenes.entries()) {
      const sec = E('section', null, 'scene'), a = s.evidence?.frame;
      sec.append(E('h2', `${i + 1}. ${s.heading}`), E('p', s.description || '(no description)'));
      if (a) {
        const sh = s.staging;
        if (s.location_choice) sec.append(E('p', 'Location chosen by hand from the candidate pool; plan score and totals describe the original solver selection.', 'meta'));
        else if (s.manual_frame) sec.append(E('p', 'Manual frame choice within assigned property; plan score refers to original solver selection.', 'meta'));
        try {
          const url = await dataUrl(`/image/${encodeURIComponent(a.shot_id)}`), im = await loadImg(url), cv = document.createElement('canvas');
          cv.width = 1280; cv.height = 720;
          drawStage(cv.getContext('2d'), 1280, 720, { imgEl: im, prov: s.provenance_label, shot: sheets[i]?.carried ? { ...sh, carried: true } : sh, t: null, editing: true, sel: -1 });
          const raw = E('img'), takes = E('div', null, 'takes');
          for (const v of ['A', 'B']) {
            const tv = s.variants?.[v] || sh, shotV = sheets[i]?.carried ? { ...tv, carried: true } : tv;
            const cv2 = document.createElement('canvas'); cv2.width = 1280; cv2.height = 720;
            drawStage(cv2.getContext('2d'), 1280, 720, { imgEl: im, prov: s.provenance_label.replace(/Variant [AB]/, `Variant ${v}`), shot: shotV, t: null, editing: true, sel: -1 });
            const fig = E('figure', null, 'take'), staged = E('img');
            staged.src = cv2.toDataURL('image/jpeg', 0.88); staged.alt = `Staged rehearsal frame, scene ${i + 1}, take ${v}`;
            fig.append(E('h4', `Take ${v}${v === snapshot.variant ? ' (active take)' : ''}: staged frame (uncalibrated screen space)`), staged);
            takes.append(fig);
          }
          raw.src = url; raw.alt = `Indexed source frame ${a.shot_id}`;
          sec.append(takes, E('h4', 'Indexed source frame'), raw);
        } catch (e) { sec.append(E('p', `Indexed image unavailable: ${e.message}`, 'unk')); }
        for (const v of ['A', 'B']) {
          const t = s.variants?.[v] || sh;
          sec.append(E('h4', `Take ${v}${v === snapshot.variant ? ' (active take)' : ''} · ${t.duration_sec}s`), E('p', t.dialogue || '(no dialogue)'));
          if (t.origin) sec.append(E('p', `Take ${v} is derived from an AUTHORED SAMPLE: pre-written blocking, not AI-generated, not an interpretation of any instruction.`, 'unk'));
          t.actors.forEach((ac) => sec.append(E('p', `${ac.name} (${ac.pose}, scale ${ac.scale}): (${ac.x0.toFixed(2)}, ${ac.y0.toFixed(2)}) → (${ac.x1.toFixed(2)}, ${ac.y1.toFixed(2)})`, 'meta')));
        }
        if (sheets[i]) sec.append(decisionNodes(E, sheets[i], snapshot.variant));
      }
      sec.append(doc.importNode(evidenceNodes(s.id, s.evidence, false), true)); doc.body.append(sec);
    }
    download(new Blob([`<!doctype html>\n${doc.documentElement.outerHTML}`], { type: 'text/html' }), 'typecast-shootpack.html');
    status('Shoot pack downloaded. Open it and use Print to save a PDF.');
  } catch (e) { status(`Shoot pack export failed: ${e.message}`, true); } finally { $('expPack').disabled = !plan(); }
}

// ---------- movie preview reel (logic lives in director-reel.js; this is only the hook) ----------
let reelCtrl = null;
function reelInput() {
  return { variant: S.variant, scenes: S.scenes.filter((s) => assignFor(s.id)).map((s) => ({ id: s.id, heading: s.heading,
    shot_id: assignFor(s.id).shot_id, prov: provText(s.id), shot: sanitizeShot(viewShot(s.id), true) })) };
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
function planningConstraints() { return S.mode === 'film' ? window.TypecastPlanning?.constraints() || {} : {}; }
const constraints = () => ({ max_locations: Math.floor(clamp($('maxLoc').value, 1, 4, 3)), require_available: $('reqAvail').checked,
  trucks: Math.floor(clamp($('trucks').value, 0, 20, 0)), cars: Math.floor(clamp($('cars').value, 0, 50, 0)), ...planningConstraints() });
async function importProject(file) {
  $('impProject').value = '';
  if (!file) return false;
  if (S.planBusy) { status('Wait for the current plan or project import to finish.', true); return false; }
  if (S.save) closeSave();
  // Claim the operation and snapshot the user's state before the first await, so nothing
  // typed during a slow file read or evidence request can be overwritten.
  busy(true);
  let rev = S.rev, scriptAtStart = $('script').value, limits = constraints();
  try {
    if (file.size > TypecastProject.MAX_BYTES) throw new Error('Project file exceeds 1 MB.');
    const project = TypecastProject.normalizeProject(await file.text());
    const target = project.mode || 'film';
    if (target !== S.mode) {
      // The file's mode decides which draft it belongs to. The other mode's work is stashed whole and untouched.
      if (S.rev !== rev || $('script').value !== scriptAtStart || JSON.stringify(constraints()) !== JSON.stringify(limits))
        throw new Error('you changed the script or staging while the file was being read, so nothing was replaced. Import again when ready');
      setMode(target, { force: true });
      rev = S.rev; scriptAtStart = $('script').value; limits = constraints();
    }
    stopPlay(); cancelGen(); clearPending();
    status('Rebuilding project evidence using the current visible location and vehicle constraints…');
    const scenes = project.scenes.map(({ id, heading, description }) => ({ id, heading, description }));
    const data = await api('/api/production/plan', { scenes, forbidden_property_ids: [], ...limits });
    PLANNING_REQUESTS.set(data, JSON.stringify(limits));
    orderPlans(data);
    // Newer user work must never be silently overwritten by a slow import.
    if (S.rev !== rev || $('script').value !== scriptAtStart)
      throw new Error('you changed the script or staging while the project was loading, so nothing was replaced. Import again when ready');
    if (JSON.stringify(constraints()) !== JSON.stringify(limits))
      throw new Error('location or vehicle constraints changed while evidence was loading, so the result would not match the visible controls. Import again');
    const restored = TypecastProject.restoreEdits(project, data);
    if (target === 'community') {                                          // community plans carry no film takes, notes, sample provenance or staging reviews
      restored.edits = {}; restored.notes = Object.create(null); restored.reviewNeeded = []; restored.swaps = Object.create(null); restored.transfers = Object.create(null);
    }
    // Commit only after validation and retrieval succeed. Imported evidence never becomes source truth.
    Object.assign(S, { scenes, resp: data, planIdx: 0, sceneId: scenes[0].id, actorIdx: 0,
      edits: restored.edits, frameOverrides: restored.frameOverrides, importReview: restored.reviewNeeded,
      swaps: restored.swaps, transfer: restored.transfers, notes: restored.notes, decisions: target === 'film' ? restored.decisions : Object.create(null), saveTx: null, alt: Object.create(null), swapUndo: null, built: { trucks: limits.trucks, cars: limits.cars, require_available: limits.require_available },
      frameChange: {}, forbidden: [], undo: null, variant: project.variant });
    $('undo').disabled = true;
    $('script').value = scenes.map((scene) => `${scene.heading} | ${scene.description}`.replace(/[\r\n]+/g, ' ')).join('\n');
    $('varA').setAttribute('aria-pressed', String(S.variant === 'A'));
    $('varB').setAttribute('aria-pressed', String(S.variant === 'B'));
    S.builtScript = $('script').value;
    if (project.mode === 'community') communityRestore(restored);
    renderAll(); renderBriefFields();
    status(project.mode === 'community'
      ? `${modeNote(data)}Project loaded with fresh evidence. ${restored.sites.length} saved site record(s) restored. Coordinator checks marked OK need re-verifying; nothing here approves a site.`
      : `${modeNote(data)}Project loaded with fresh evidence. ${restored.restored} scene draft(s) restored to exact saved frames; ${restored.reviewNeeded.length} retained for review.`, project.mode !== 'community' && !!restored.reviewNeeded.length);
    return true;
  } catch (e) { status(`Project not loaded; existing work kept: ${e.message}`, true); return false; }
  finally { busy(false); }
}
$('impProject').addEventListener('change', (event) => importProject(event.target.files[0]));

// ---------- events ----------
$('build').addEventListener('click', () => build(false));
$('script').addEventListener('input', () => { S.rev++; renderParse(); });
$('demo').addEventListener('click', () => { S.rev++; $('script').value = S.mode === 'community' ? COMM_DEMO : DEMO; renderParse(); status(S.mode === 'community' ? 'Example needs loaded. Press Find candidate sites; the summary states whether results are live or mock fixtures.' : 'Demo script loaded. Press Build plan; the plan summary states whether results are live or mock fixtures.'); });
$('planSel').addEventListener('change', (e) => {
  const prev = assignMap(); stopPlay(); cancelGen(); clearPending();
  S.planIdx = clamp(e.target.value, 0, (S.resp?.plans.length || 1) - 1, 0); noteFrameChanges(prev); renderAll();
});
$('clearRej').addEventListener('click', () => { S.forbidden = []; renderPlan(); status('Rejections cleared. Build plan again to apply.'); });
$('reject').addEventListener('click', reject);
$('planner').addEventListener('click', async (event) => {
  const out = $('plannerOut'), a = assignFor(S.sceneId);
  if (!out || !a) return;
  event.preventDefault();
  out.hidden = false; out.replaceChildren(el('p', { class: 'meta', text: 'Loading camera metrics…' }));
  const sid = S.sceneId, shotId = a.shot_id;
  try {
    const r = await fetch(`/api/plan/${encodeURIComponent(shotId)}?heading=0&focal=35`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const m = await r.json();
    if (sid !== S.sceneId || assignFor(sid)?.shot_id !== shotId) return;
    const rows = {}; for (const [k, v] of Object.entries(m)) if (v == null || ['string', 'number', 'boolean'].includes(typeof v)) rows[k] = v;
    out.replaceChildren(kv('Camera metrics · heading 0° assumed, scan-relative, unverified', rows),
      el('p', { class: 'meta', text: 'Source: /api/plan. Unknown means the source did not supply it; this is not a clearance approval.' }));
  } catch (e) { out.replaceChildren(el('p', { class: 'warn', text: `Camera metrics unavailable: ${e.message}` })); }
});
let scanViewfinder;
$('lookAround').addEventListener('click', async () => {
  const assignment = assignFor(S.sceneId);
  if (!assignment || S.planBusy) return;
  if (S.resp?.mode === 'mock') {
    return status('Look around and AI dressing need a real indexed scan point with verified 360° geometry. Mock fixture frames have neither, so nothing is opened.', true);
  }
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
  } catch (error) { status('Scan view unavailable (the frame may lack verified 360° geometry). The indexed rehearsal frame is still available.', true); }
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
  if (S.mode === 'community') return;
  if (S.compare) return status('Comparison is read-only. Choose take A or B (or turn Compare off) to move stand-ins.');
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
  if (S.compare || S.mode === 'community') return;
  const a = curActor(), d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[e.key];
  if (!a || !d) return;
  e.preventDefault(); const [fx, fy] = e.shiftKey ? ['x1', 'y1'] : ['x0', 'y0'], step = e.altKey ? 0.05 : 0.01;
  a[fx] = r3(clamp(a[fx] + d[0] * step, 0, 1, a[fx])); a[fy] = r3(clamp(a[fy] + d[1] * step, 0, 1, a[fy]));
  syncActor(a); edited();
});
$('cmpAB').addEventListener('click', toggleCompare);
$('noteDressing').addEventListener('input', (e) => setNote('dressing', e.target.value));
$('noteGroup').addEventListener('input', (e) => { setNote('group', e.target.value); e.target.value = S.notes[S.sceneId]?.group || ''; });
$('gen').addEventListener('click', generate);
$('loadSample').addEventListener('click', loadSample);
$('applyB').addEventListener('click', applyB);
$('discard').addEventListener('click', () => { clearPending(); status('Proposal discarded. Nothing changed.'); });
$('undo').addEventListener('click', undoApply);
$('expPng').addEventListener('click', () => {
  stopPlay(); drawSingle();   // always the active take, never the comparison layout
  try { cv.toBlob((b) => (b ? download(b, `typecast-${S.sceneId || 'stage'}-${S.variant}.png`) : status('PNG export failed.', true)), 'image/png'); }
  catch (e) { status(`PNG export failed: ${e.message}`, true); }
  draw();
  if (S.compare) status(`Stage PNG saved for active take ${S.variant} only (not the comparison view).`);
});
$('expJson').addEventListener('click', () => {
  const proj = exportSnapshot();
  download(new Blob([JSON.stringify(proj, null, 2)], { type: 'application/json' }), 'typecast-project.json');
  status('Project JSON downloaded.');
});
$('expPack').addEventListener('click', () => (S.mode === 'community' ? exportBrief() : exportPack()));
$('expReel').addEventListener('click', exportReel);
$('cancelReel').addEventListener('click', () => reelCtrl && reelCtrl.abort());
window.addEventListener('pagehide', () => { if (rec) rec.stop(); if (reelCtrl) reelCtrl.abort(); stopPlay(); });

// ================= Save the scene (film mode only) =================
// One coherent interaction: keep the current candidate and both takes, add a real requirement, let the planner re-check the pool,
// review a bounded before/after comparison, and only then apply it. Nothing changes until "Apply alternative", and Undo restores the
// exact previous state. It uses the existing planner request; it is not an agent and no model is called.
let saveTok = 0;
const saveCtx = (sid) => { const a = assignFor(sid); return { sid, shot: a?.shot_id, prop: a?.property_id, resp: S.resp, script: $('script').value, cons: JSON.stringify(constraints()), forb: JSON.stringify(S.forbidden), planIdx: S.planIdx, mode: S.mode }; };
const saveCtxValid = (c) => !!c && c.mode === S.mode && c.sid === S.sceneId && c.resp === S.resp && c.planIdx === S.planIdx && c.script === $('script').value
  && c.cons === JSON.stringify(constraints()) && c.forb === JSON.stringify(S.forbidden) && assignFor(c.sid)?.shot_id === c.shot && assignFor(c.sid)?.property_id === c.prop;
function closeSave(why) {
  if (S.save?.ctrl) S.save.ctrl.abort();
  saveTok++; S.save = null; renderSavePanel();
  if (why) status(why);
}
function openSave() {
  if (S.mode !== 'film') return;
  if (S.save) return closeSave();
  const sid = S.sceneId, a = sid && assignFor(sid);
  if (!a || S.planBusy || reelCtrl) return status('Build a plan and wait for it to finish before saving a scene.', true);
  cancelGen(); clearPending(); stopPlay();
  const c = constraints();
  S.save = { phase: 'form', sid, ctx: saveCtx(sid), form: { trucks: c.trucks, cars: c.cars, reqAvail: c.require_available }, tok: ++saveTok };
  renderSavePanel(); S.save?.els?.trucks?.focus?.();
}
function readSaveForm() {
  const e = S.save?.els; if (!e) return { error: 'The form is not open.' };
  const t = Number(e.trucks.value), c = Number(e.cars.value), form = { trucks: Math.floor(t), cars: Math.floor(c), reqAvail: e.avail.checked };
  if (!Number.isInteger(t) || t < 0 || t > 20) return { error: 'Trucks must be a whole number from 0 to 20.' };
  if (!Number.isInteger(c) || c < 0 || c > 50) return { error: 'Cars must be a whole number from 0 to 50.' };
  return { form };
}
async function runSave() {
  const sv = S.save; if (!sv || sv.phase === 'loading') return;
  const r = readSaveForm(); if (r.error) { sv.error = r.error; return renderSavePanel(); }
  const req = { trucks: r.form.trucks, cars: r.form.cars, require_available: r.form.reqAvail };
  if (!saveCtxValid(sv.ctx)) { sv.phase = 'review'; sv.stale = true; return renderSavePanel(); }
  if (req.trucks + req.cars === 0 && !req.require_available) {              // nothing to check: no request is sent
    sv.outcome = TypecastChecks.saveSceneOutcome({ sid: sv.sid, req, before: { shot_id: sv.ctx.shot, property_id: sv.ctx.prop }, newResp: null }); sv.req = req; sv.phase = 'review'; return renderSavePanel();
  }
  const body = { scenes: S.scenes.map(({ id, heading, description }) => ({ id, heading, description })), max_locations: clamp($('maxLoc').value, 1, 4, 3),
    forbidden_property_ids: [...S.forbidden], require_available: req.require_available, trucks: req.trucks, cars: req.cars, ...planningConstraints() };
  sv.form = r.form; sv.req = req; sv.error = ''; sv.phase = 'loading'; sv.ctrl = new AbortController(); const tok = sv.tok; renderSavePanel();
  try {
    const data = await api('/api/production/plan', body, sv.ctrl.signal);
    PLANNING_REQUESTS.set(data, JSON.stringify({ ...constraints(), trucks: body.trucks, cars: body.cars, require_available: body.require_available }));
    if (S.save !== sv || tok !== saveTok) return;
    if (!Array.isArray(data.scenes) || !Array.isArray(data.plans)) throw new Error('Malformed plan response');
    if (data.mode !== S.resp?.mode) throw new Error('The data source mode changed, so the two plans are not comparable');
    if (!saveCtxValid(sv.ctx)) { sv.phase = 'review'; sv.stale = true; sv.ctrl = null; return renderSavePanel(); }
    applyForbidden(data); orderPlans(data);
    const a = assignFor(sv.sid), old = S.built || constraints();
    const maxLoc = clamp($('maxLoc').value, 1, 4, 3);
    sv.outcome = TypecastChecks.saveSceneOutcome({ sid: sv.sid, req, oldReq: { trucks: old.trucks, cars: old.cars, require_available: old.require_available }, before: { shot_id: a.shot_id, property_id: a.property_id },
      oldCand: candFor(sv.sid, a.shot_id), newResp: data, forbidden: [...S.forbidden], maxLocations: maxLoc, oldAssign: Object.fromEntries(S.scenes.map((s) => { const x = assignFor(s.id); return [s.id, x ? { shot_id: x.shot_id, property_id: x.property_id } : null]; }).filter(([, v]) => v)) });
    sv.resp = data; sv.phase = 'review'; sv.ctrl = null;
  } catch (e) {
    if (e.name === 'AbortError' || S.save !== sv || tok !== saveTok) return;
    sv.phase = 'error'; sv.error = `Could not check the pool: ${e.message}. Nothing changed.`; sv.ctrl = null;
  }
  renderSavePanel();
}
const np = (o) => Object.assign(Object.create(null), o || {});
const deep = (o) => JSON.parse(JSON.stringify(o ?? null));
function snapshotAll() {
  const inp = { maxLoc: $('maxLoc').value, trucks: $('trucks').value, cars: $('cars').value, reqAvail: $('reqAvail').checked };
  return { inp, resp: S.resp, planIdx: S.planIdx, forbidden: [...S.forbidden], built: deep(S.built), builtScript: S.builtScript, sceneId: S.sceneId,
    swaps: deep(S.swaps), transfer: deep(S.transfer), alt: deep(S.alt), edits: deep(S.edits), frameChange: deep(S.frameChange), frameOverrides: deep(S.frameOverrides),
    importReview: deep(S.importReview), decisions: deep(S.decisions), notes: deep(S.notes), swapUndo: deep(S.swapUndo), undo: deep(S.undo), actorIdx: S.actorIdx, variant: S.variant };
}
function restoreAll(t) {
  $('maxLoc').value = t.inp.maxLoc; $('trucks').value = t.inp.trucks; $('cars').value = t.inp.cars; $('reqAvail').checked = t.inp.reqAvail;
  S.resp = t.resp; S.planIdx = t.planIdx; S.forbidden = [...t.forbidden]; S.built = deep(t.built); S.builtScript = t.builtScript; S.sceneId = t.sceneId; S.actorIdx = t.actorIdx; S.variant = t.variant;
  S.swaps = np(deep(t.swaps)); S.transfer = np(deep(t.transfer)); S.alt = np(deep(t.alt)); S.edits = deep(t.edits) || {}; S.frameChange = deep(t.frameChange) || {}; S.frameOverrides = deep(t.frameOverrides) || {};
  S.importReview = deep(t.importReview) || []; S.decisions = np(deep(t.decisions)); S.notes = np(deep(t.notes)); S.swapUndo = deep(t.swapUndo); S.undo = deep(t.undo);
  $('undo').disabled = !S.undo;
}
function applySave() {
  const sv = S.save, o = sv?.outcome;
  if (!sv || sv.phase !== 'review' || !o || o.kind !== 'alternative' || !o.afterCand || !sv.resp) return;
  if (!saveCtxValid(sv.ctx)) { sv.stale = true; return renderSavePanel(); }
  const sid = sv.sid, cand = o.afterCand;
  // The chosen candidate must be assigned in a complete, valid revised plan, never an id from an older pool.
  const inPool = (sv.resp.scenes.find((x) => x.id === sid)?.candidates || []).some((c) => c === cand && c.eligible !== false && !S.forbidden.includes(c.shot.property_id));
  const plan0 = sv.resp.plans?.[0], assigned = (plan0?.assignments || []).find((a) => a.scene_id === sid);
  const sat = TypecastChecks.satisfaction(TypecastChecks.candidateFacts(cand), sv.req);
  const allCovered = S.scenes.every((s) => (plan0?.assignments || []).some((a) => a.scene_id === s.id) && !(plan0?.uncovered_scene_ids || []).includes(s.id));
  const withinMax = new Set((plan0?.assignments || []).map((a) => a.property_id)).size <= clamp($('maxLoc').value, 1, 4, 3);
  const allAssignValid = (plan0?.assignments || []).every((a) => {
    if (S.forbidden.includes(a.property_id)) return false;
    const cObj = sv.resp.scenes?.find((x) => x.id === a.scene_id)?.candidates?.find((c) => c.shot && c.shot.shot_id === a.shot_id && c.shot.property_id === a.property_id && c.eligible !== false);
    if (!cObj) return false;
    return TypecastChecks.satisfaction(TypecastChecks.candidateFacts(cObj), sv.req).satisfied;
  });
  if (!inPool || !assigned || assigned.shot_id !== cand.shot.shot_id || assigned.property_id !== cand.shot.property_id || !sat.satisfied || !allCovered || !withinMax || !allAssignValid) { sv.stale = true; return renderSavePanel(); }
  const tx = snapshotAll(), before = assignFor(sid), prev = assignMap(), oldKey = keyOf(sid), oldReq = S.built || constraints();
  stopPlay(); cancelGen(); clearPending();
  // 1. the request controls and the plan change together, so what you see is what was planned
  $('trucks').value = String(sv.req.trucks); $('cars').value = String(sv.req.cars); $('reqAvail').checked = sv.req.require_available;
  S.resp = sv.resp; S.planIdx = 0; S.frameOverrides = {}; S.swaps = np(); S.swapUndo = null; S.built = { trucks: sv.req.trucks, cars: sv.req.cars, require_available: sv.req.require_available };
  noteFrameChanges(prev); delete S.frameChange[sid];
  // 2. this scene moves to the chosen candidate; both takes come along as unreviewed drafts and nothing is overwritten
  const k = `${S.planIdx}::${sid}`, newKey = `${sid}::${cand.shot.shot_id}`;
  S.swaps[k] = { shot_id: cand.shot.shot_id, property_id: cand.shot.property_id, from_shot_id: before.shot_id, from_property_id: before.property_id, via: 'save' };
  if (S.edits[oldKey] && hasWork(S.edits[oldKey])) {
    if (!S.edits[newKey] || !hasWork(S.edits[newKey])) { S.edits[newKey] = clone(S.edits[oldKey]); S.transfer[newKey] = { from_shot_id: before.shot_id, from_property_id: before.property_id, reviewed: false }; }
    else if (JSON.stringify(S.edits[newKey]) !== JSON.stringify(S.edits[oldKey])) S.swaps[k].dest_kept = true;
  }
  // 3. the historical decision record
  S.decisions[sid] = TypecastChecks.decisionRecord(o, { trucks: oldReq.trucks, cars: oldReq.cars, require_available: oldReq.require_available }, sv.req, new Date().toISOString());
  S.rev++; S.save = null; saveTok++; renderAll();
  S.saveTx = { sid, tx, rev: S.rev };
  const reqDesc = sv.req.trucks > 0 && sv.req.cars > 0 ? `${sv.req.trucks} truck${sv.req.trucks === 1 ? '' : 's'} and ${sv.req.cars} car${sv.req.cars === 1 ? '' : 's'}`
    : sv.req.trucks > 0 ? `${sv.req.trucks} truck${sv.req.trucks === 1 ? '' : 's'}`
    : sv.req.cars > 0 ? `${sv.req.cars} car${sv.req.cars === 1 ? '' : 's'}`
    : 'an available listing';
  const takeMsg = S.swaps[k].dest_kept ? 'Existing staging on this frame was kept.' : 'Both takes were copied as unreviewed drafts; the previous frame and its takes are kept.';
  status(`Applied: scene ${sceneNumber(sid)} now uses ${safeId(cand.shot.property_id)} for ${reqDesc}. ${takeMsg} Undo restores everything.`);
  renderSwapNotice();
}
function undoSave() {
  const t = S.saveTx;
  if (!t || t.rev !== S.rev) return status('Undo is available only until you change something else; use Back to planned location instead.', true);
  stopPlay(); cancelGen(); clearPending(); closeSave();
  restoreAll(t.tx); S.saveTx = null; S.rev++; renderAll();
  status('Save the scene was undone: the previous plan, requirements, frame, takes and notes are exactly as they were.');
}
const saveOutcomeText = {
  already: 'The current frame already satisfies these requirements according to the planner data (estimates are not approvals). Nothing to change.',
};
function renderSavePanel() {
  const panel = $('savePanel'), body = $('saveBody'), sv = S.save;
  $('saveBtn').setAttribute('aria-expanded', String(!!sv)); $('saveBtn').disabled = S.mode !== 'film' || S.planBusy || !S.sceneId || !assignFor(S.sceneId);
  if (!sv || S.mode !== 'film') { panel.hidden = true; body.replaceChildren(); return; }
  panel.hidden = false; body.replaceChildren();
  const cancel = el('button', { type: 'button', text: sv.phase === 'review' || sv.phase === 'error' ? 'Close' : 'Cancel' }); cancel.addEventListener('click', () => closeSave());
  const a = assignFor(sv.sid), c = a && candFor(sv.sid, a.shot_id), f = c && TypecastChecks.candidateFacts(c);
  const here = el('p', { class: 'meta', text: `Scene ${sceneNumber(sv.sid)} now uses ${safeId(a?.property_id)} (frame ${safeId(a?.shot_id)}). Both takes are kept; nothing changes until you apply an alternative.` });
  if (sv.stale) {
    body.append(el('p', { class: 'warn', text: 'The script, requirements, rejections, scene or plan changed since you opened this. Nothing was replaced. Check again from the current state.' }), el('div', { class: 'row' }, (() => { const b = el('button', { type: 'button', class: 'primary', text: 'Start again' }); b.addEventListener('click', () => { closeSave(); openSave(); }); return b; })(), cancel));
    return;
  }
  if (sv.phase === 'form') {
    const live = el('p', { id: 'svLive', class: 'chk chk-unknown', 'aria-live': 'polite' });
    const upd = () => {
      const r = readSaveForm(); if (r.error) { live.textContent = r.error; return; }
      const fit = TypecastChecks.fitCheck({ scene: S.scenes.find((x) => x.id === sv.sid), cand: c, built: { trucks: r.form.trucks, cars: r.form.cars, require_available: r.form.reqAvail }, mode: S.resp?.mode });
      const veh = r.form.trucks + r.form.cars > 0, rows = fit.rows.filter((x) => (veh && /Parking/i.test(x.label)) || (r.form.reqAvail && /availability/i.test(x.label)));
      live.textContent = rows.length ? rows.map((x) => `${TypecastChecks.KIND_LABEL[x.kind]}: ${x.label}. ${x.detail}`).join(' ') : 'No vehicle or availability requirement is set yet.';
    };
    const mk = (label, v, max) => { const input = el('input', { type: 'number', min: '0', max: String(max), value: String(v), inputmode: 'numeric', 'aria-label': label }); return { input, label: el('label', {}, `${label} `, input) }; };
    const tr = mk('Trucks', sv.form.trucks, 20), ca = mk('Crew cars', sv.form.cars, 50), av = el('input', { type: 'checkbox', 'aria-label': 'Require an available listing' });
    av.checked = !!sv.form.reqAvail; sv.els = { trucks: tr.input, cars: ca.input, avail: av };
    body.append(here, el('div', { class: 'constraints' }, tr.label, ca.label), el('label', { class: 'check' }, av, ' Require an available listing'), live,
      el('p', { class: 'meta', text: `This re-plans the whole script with these requirements (this planner works on whole plans); max locations ${clamp($('maxLoc').value, 1, 4, 3)} and ${S.forbidden.length} rejected location${S.forbidden.length === 1 ? '' : 's'} stay. Unknown capacity is never counted as met.` }));
    for (const x of [tr.input, ca.input, av]) x.addEventListener('input', upd);
    upd();
    const go = el('button', { type: 'button', class: 'primary', text: 'Find an alternative' }); go.addEventListener('click', runSave);
    body.append(...(sv.error ? [el('p', { class: 'warn', text: sv.error })] : []), el('div', { class: 'row' }, go, cancel));
    return;
  }
  if (sv.phase === 'loading') { body.append(here, el('p', { text: 'Checking the candidate pool with these requirements…', role: 'status' }), el('div', { class: 'row' }, cancel)); return; }
  if (sv.phase === 'error') { body.append(el('p', { class: 'warn', text: sv.error }), el('div', { class: 'row' }, cancel)); return; }
  // review
  const o = sv.outcome, req = sv.req;
  const reqText = `${req.trucks} truck${req.trucks === 1 ? '' : 's'}, ${req.cars} car${req.cars === 1 ? '' : 's'}${req.require_available ? ', available listing' : ''}`;
  body.append(el('h3', { text: `Requirement: ${reqText}` }));
  const thumbBox = (fct, title) => el('figure', { class: 'save-card' }, fct ? el('img', { class: 'thumb', alt: `${title} frame ${fct.shot_id}`, src: `/image/${encodeURIComponent(fct.shot_id)}` }) : '', el('figcaption', { text: `${title}: ${fct ? safeId(fct.property_id) : 'none'}` }));
  if (o.kind === 'alternative') {
    body.append(el('div', { class: 'save-compare' }, thumbBox(o.before, 'Before'), thumbBox(o.after, 'Proposed after')),
      el('ul', { class: 'chk-list' }, ...o.differences.map((d) => el('li', { class: 'chk', text: d }))),
      el('h4', { text: 'Still unresolved' }), el('ul', { class: 'chk-list' }, ...o.unresolved.map((d) => el('li', { class: 'chk chk-unknown', text: d }))),
      el('p', { class: 'meta', text: `Scope: ${o.planChanges.length ? `the whole plan is replaced, and ${o.planChanges.length} other scene${o.planChanges.length === 1 ? ' moves' : 's move'} too (their takes stay with their old frames).` : 'the whole plan is re-planned; no other scene changes frame.'} This compares planner data, not shootability, and is not an approval.` }));
    const apply = el('button', { type: 'button', class: 'primary', text: 'Apply alternative' }); apply.addEventListener('click', applySave);
    body.append(el('div', { class: 'row' }, apply, (() => { const k = el('button', { type: 'button', text: 'Keep original' }); k.addEventListener('click', () => closeSave('Kept the original. Nothing changed.')); return k; })()));
    return;
  }
  const msg = o.kind === 'already' ? saveOutcomeText.already : `No better candidate: ${o.reasons.join(' ')}`;
  body.append(thumbBox(o.before, 'Current'), el('p', { role: 'status', text: msg }),
    ...(o.before ? [el('p', { class: 'meta', text: `Current candidate under these requirements: ${o.before.excluded ? 'ruled out by the planner' : o.before.sat.parking === 'unknown' ? 'capacity unknown' : o.before.sat.parking === 'unmet' ? 'capacity below the requirement' : o.before.sat.parking === 'met' ? `${o.before.parking_status} capacity covers it (approval unknown)` : 'no vehicle requirement'}.` })] : []),
    el('p', { class: 'meta', text: 'Nothing was changed and no result is saved. Add the data to the sources, relax the requirement, or check on site.' }), el('div', { class: 'row' }, cancel));
}
$('saveBtn').addEventListener('click', openSave);
function refreshSaveStale() { if (S.save && S.save.phase === 'review' && !S.save.stale && !saveCtxValid(S.save.ctx)) { S.save.stale = true; renderSavePanel(); } }
for (const id of ['trucks', 'cars', 'maxLoc', 'reqAvail', 'script']) $(id).addEventListener(id === 'maxLoc' || id === 'reqAvail' ? 'change' : 'input', refreshSaveStale);
// a saved decision is a historical review note, never current source truth
function decisionHistoryNodes(sid) {
  const r = S.decisions[sid]; if (!r) return null;
  const a = assignFor(sid), cur = S.built || constraints();
  const box = el('section', { class: 'ev save-record' }, el('h4', { text: 'Saved decision (historical record)' }));
  box.append(el('p', { class: 'meta', text: `Recorded ${r.decided_at.slice(0, 10)} for ${r.revised.trucks} truck${r.revised.trucks === 1 ? '' : 's'}, ${r.revised.cars} car${r.revised.cars === 1 ? '' : 's'}${r.revised.require_available ? ', available listing' : ''}. These are the facts captured then; they are not current source data and not an approval.` }),
    el('p', { text: `${r.before ? safeId(r.before.property_id) : 'none'} (frame ${r.before ? safeId(r.before.shot_id) : 'none'}) → ${r.after ? safeId(r.after.property_id) : 'none'} (frame ${r.after ? safeId(r.after.shot_id) : 'none'}).` }),
    el('ul', { class: 'chk-list' }, ...r.differences.map((d) => el('li', { class: 'chk', text: d }))));
  if (r.after && (!a || a.shot_id !== r.after.shot_id)) box.append(el('p', { class: 'warn', text: 'This scene no longer uses the frame that decision chose.' }));
  if (cur.trucks !== r.revised.trucks || cur.cars !== r.revised.cars || !!cur.require_available !== r.revised.require_available) box.append(el('p', { class: 'warn', text: 'Your current requirement controls differ from the ones this decision used. Set them again to re-check the fit rows.' }));
  return box;
}

// ================= mode: Film production | Community planning =================
// Community planning is pre-incident candidate-site review for volunteer and supply coordination. It reuses the same
// evidence, retrieval and review engine and adds human-reported coordinator checks. It never routes evacuations,
// approves shelters, or turns floor area, photos, listings or parking into capacity, safety or availability.
const COMM_BADGE = 'PREPAREDNESS PLANNING · CANDIDATE SITE · NOT AN APPROVED SITE';
const COMM_DEMO = [
  'Supply distribution hub', 'Large open indoor floor where volunteers sort and hand out supplies, at least 150 m2, loading access for two supply trucks, away from the main road.', '',
  'Volunteer check-in and briefing', 'A quiet room for about 30 volunteers to check in and be briefed, an accessible entrance and restrooms nearby.', '',
  'Cold storage and staging', 'Floor area for pallets and a vehicle bay for refrigerated trucks, no more than 600 m2.',
].join('\n');
const MODE_KEYS = ['saveTx', 'decisions', 'builtScript', 'scenes', 'resp', 'planIdx', 'sceneId', 'variant', 'forbidden', 'edits', 'frameChange', 'frameOverrides', 'importReview', 'actorIdx',
  'undo', 'swaps', 'transfer', 'alt', 'swapUndo', 'notes', 'built', 'compare', 'comm', 'brief'];
function freshMode(m) {
  return { saveTx: null, decisions: Object.create(null), builtScript: '', scenes: [], resp: null, planIdx: 0, sceneId: null, variant: 'A', forbidden: [], edits: {}, frameChange: {}, frameOverrides: {}, importReview: [], actorIdx: 0,
    undo: null, swaps: Object.create(null), transfer: Object.create(null), alt: Object.create(null), swapUndo: null, notes: Object.create(null), built: null, compare: false,
    comm: Object.create(null), brief: { reviewer: '', date: '', notes: '' },
    inputs: { script: m === 'film' ? DEMO : '', maxLoc: '3', trucks: '0', cars: '0', reqAvail: false } };
}
const MODES = { film: null, community: null };            // the stashed state of the mode that is not showing
function captureMode() {
  const o = {}; for (const k of MODE_KEYS) o[k] = S[k];
  o.inputs = { script: $('script').value, maxLoc: $('maxLoc').value, trucks: $('trucks').value, cars: $('cars').value, reqAvail: $('reqAvail').checked };
  return o;
}
function applyModeState(o) {
  for (const k of MODE_KEYS) S[k] = o[k];
  $('script').value = o.inputs.script; $('maxLoc').value = o.inputs.maxLoc; $('trucks').value = o.inputs.trucks; $('cars').value = o.inputs.cars; $('reqAvail').checked = !!o.inputs.reqAvail;
}
function applyModeUI() {
  const comm = S.mode === 'community';
  document.body.setAttribute('data-mode', S.mode);
  $('modeFilm').setAttribute('aria-pressed', String(!comm)); $('modeComm').setAttribute('aria-pressed', String(comm));
  document.title = comm ? 'Typecast — Community planning' : 'Typecast — Director\'s Room';
  $('h-script').textContent = comm ? 'Site needs' : 'Script';
  $('demo').textContent = comm ? 'Load example needs' : 'Load demo script';
  $('scriptHint').textContent = comm ? 'Describe each site you need as a short paragraph: a title line, then what it must offer. Separate needs with a blank line. Up to 8.'
    : 'Paste a screenplay (scenes start with INT. or EXT.) or write one scene per line: HEADING | description. Up to 8 scenes.';
  $('script').placeholder = comm ? 'Supply distribution hub\nLarge open indoor floor for volunteers, at least 150 m2, loading access for two trucks.' : '';
  $('lblTrucks').textContent = comm ? 'Supply trucks' : 'Trucks'; $('lblCars').textContent = comm ? 'Volunteer cars' : 'Crew cars';
  $('build').textContent = comm ? 'Find candidate sites' : 'Build plan';
  $('h-plan').textContent = comm ? 'Candidate sites' : 'Plan'; $('h-scenes').textContent = comm ? 'Needs' : 'Scenes';
  $('reject').textContent = comm ? 'Rule out site' : 'Reject location'; $('clearRej').textContent = comm ? 'Clear ruled-out sites' : 'Clear rejections';
  $('expPack').textContent = comm ? 'Site brief (printable)' : 'Shoot pack';
  $('modeHint').textContent = comm ? 'Planning aid for volunteer and supply sites before an incident. Not for evacuation or emergency routing.' : 'Staging, locations and a shoot pack for a film.';
  $('stageCaption').replaceChildren(...(comm
    ? [el('span', { class: 'caption-label', text: 'Candidate site review' }), el('span', { class: 'caption-label', text: 'Not an approved site' }), el('span', { text: 'The frame is an indexed scan image, not a current photo. Owner permission, capacity, exits and hazards must be checked on site.' })]
    : [el('span', { class: 'caption-label', text: 'Uncalibrated screen-space rehearsal' }), el('span', { class: 'caption-label', text: 'Geometric fit: unknown' }), el('span', { text: 'Drag a stand-in to place it; drag its ring to set where it walks. Positions are on screen, not measured in the room.' })]));
  $('stage').setAttribute('aria-label', comm ? 'Real indexed frame of the selected candidate site.' : 'Stage. Drag an actor body to set start, the ring to set end. Arrow keys nudge selected actor start, Shift plus arrows nudge end.');
  if (!S.resp && $('stageLoc')) $('stageLoc').textContent = comm ? 'Find candidate sites to put real indexed rooms in front of you.' : 'Build a plan to put real indexed rooms on the stage.';
  window.TypecastTabs?.select(comm ? 'tab-site' : 'tab-shot');
  $('undo').disabled = !S.undo;
  renderBriefFields();
}
function setMode(m, opts = {}) {
  if (m !== 'film' && m !== 'community') return false;
  if (m === S.mode) return true;
  if (!opts.force && (S.planBusy || reelCtrl)) { status('Wait for the plan or reel to finish before switching mode.', true); return false; }
  stopPlay(); cancelGen(); clearPending(); endDrag(); if (S.save) closeSave();
  MODES[S.mode] = captureMode();                           // film work is stashed whole, never edited by community mode
  const had = !!MODES[m];
  S.mode = m; applyModeState(MODES[m] || freshMode(m)); MODES[m] = null; S.rev++;
  applyModeUI(); renderAll(); renderParse();
  if (!had && draftState.ready && !opts.force) restoreDraft(m);          // first visit to this mode: offer its own saved draft
  status(m === 'community' ? 'Community planning: candidate-site review for volunteer and supply coordination. Your film work is kept separately.' : 'Film production. Your community planning draft is kept separately.');
  return true;
}
$('modeFilm').addEventListener('click', () => setMode('film'));
$('modeComm').addEventListener('click', () => setMode('community'));

// ---- community records: needs belong to a need, checks belong to one candidate site ----
const needRec = (sid) => (S.comm[`need:${sid}`] ||= { requested: null, note: '' });
// Scene and property ids never contain '|', so the first bar splits a site key without ambiguity (ids may contain colons).
const siteKey = (sid, pid) => `site:${sid}|${pid}`;
const parseSiteKey = (key) => { const bar = key.indexOf('|'); return bar < 0 ? null : { sid: key.slice(5, bar), pid: key.slice(bar + 1) }; };
const siteRec = (sid, pid) => (S.comm[siteKey(sid, pid)] ||= { checks: Object.create(null), verified: null, tasks: [] });
const curSite = () => { const a = S.mode === 'community' && S.sceneId ? assignFor(S.sceneId) : null; return a ? { sid: S.sceneId, pid: a.property_id } : null; };
function siteChecksSummary(rec) { return TypecastChecks.communityStatusText(rec); }
function renderSite() {
  if (S.mode !== 'community') return;
  const cs = curSite(), sc = S.scenes.find((s) => s.id === S.sceneId);
  const inputs = ['siteReq', 'siteNote', 'siteCap', 'siteCapSrc', 'taskAdd'];
  $('siteTitle').textContent = sc ? `Need ${sceneNumber(sc.id)} · ${sc.heading}` : 'Site need';
  if (!cs) {
    for (const id of inputs) $(id).disabled = true;
    $('siteChecks').replaceChildren(el('p', { class: 'meta', text: S.resp ? 'No candidate site is assigned to this need in this plan. Rebuild, or rule out fewer sites.' : 'Find candidate sites first.' }));
    $('siteTasks').replaceChildren(); $('siteChecksSummary').textContent = 'Coordinator checks'; return;
  }
  for (const id of inputs) $(id).disabled = false;
  const need = needRec(cs.sid), rec = siteRec(cs.sid, cs.pid);
  $('siteReq').value = need.requested == null ? '' : String(need.requested); $('siteNote').value = need.note;
  $('siteCap').value = rec.verified && rec.verified.capacity != null ? String(rec.verified.capacity) : ''; $('siteCapSrc').value = rec.verified ? rec.verified.source : '';
  renderCapNote(rec);
  const rows = TypecastChecks.COMMUNITY_CHECKS.map((c) => {
    const cur = rec.checks[c.key] || { state: 'unknown', note: '' };
    const sel = el('select', { id: `chk-${c.key}`, 'aria-label': `${c.label}: status` });
    for (const [v, t] of Object.entries(TypecastChecks.CHECK_STATE_LABEL)) sel.append(el('option', { value: v, text: t }));
    sel.value = TypecastChecks.isState(cur.state) ? cur.state : 'unknown';
    const note = el('input', { id: `chkn-${c.key}`, maxlength: '200', placeholder: 'Note, source or who you asked', 'aria-label': `${c.label}: note`, value: cur.note || '' });
    const stale = el('small', { class: 'unk', text: cur.stale && cur.state === 'ok' ? ' restored from a file; re-verify' : '' });
    const upd = () => {
      S.rev++; const r = siteRec(cs.sid, cs.pid);
      r.checks[c.key] = { state: sel.value, note: TypecastChecks.textOf(note.value, 200) };            // a change by you clears "restored"
      stale.textContent = ''; $('siteChecksSummary').textContent = `Coordinator checks · ${siteChecksSummary(r)}`; renderChecks();
    };
    sel.addEventListener('change', upd); note.addEventListener('input', upd);
    return el('div', { class: 'chk-row' }, el('label', { for: sel.id, text: c.label }), stale, sel, note);
  });
  $('siteChecks').replaceChildren(el('p', { class: 'meta', text: 'Everything here is reported by you. Typecast cannot verify it, and nothing marks a site approved. Unknown is the default.' }), ...rows);
  $('siteChecksSummary').textContent = `Coordinator checks · ${siteChecksSummary(rec)}`;
  renderTasks(cs, rec);
}
function renderTasks(cs, rec) {
  const box = $('siteTasks');
  box.replaceChildren(...rec.tasks.map((t, i) => {
    const text = el('input', { maxlength: '120', value: t.text, 'aria-label': `Follow-up ${i + 1}` }), owner = el('input', { maxlength: '40', value: t.owner, placeholder: 'Who', 'aria-label': `Follow-up ${i + 1} owner` });
    const del = el('button', { type: 'button', class: 'quiet', 'aria-label': `Remove follow-up ${i + 1}`, text: 'Remove' });
    text.addEventListener('input', () => { S.rev++; t.text = TypecastChecks.textOf(text.value, 120); });
    owner.addEventListener('input', () => { S.rev++; t.owner = TypecastChecks.textOf(owner.value, 40); });
    del.addEventListener('click', () => { S.rev++; rec.tasks.splice(i, 1); renderTasks(cs, rec); });
    return el('div', { class: 'task-row' }, text, owner, del);
  }));
  $('taskAdd').disabled = rec.tasks.length >= 6;
}
$('taskAdd').addEventListener('click', () => { const cs = curSite(); if (!cs) return; const rec = siteRec(cs.sid, cs.pid); if (rec.tasks.length >= 6) return; S.rev++; rec.tasks.push({ text: '', owner: '' }); renderTasks(cs, rec); });
$('siteReq').addEventListener('input', (e) => { const cs = curSite(); if (!cs) return; S.rev++; needRec(cs.sid).requested = TypecastChecks.countOf(e.target.value); });
$('siteNote').addEventListener('input', (e) => { const cs = curSite(); if (!cs) return; S.rev++; needRec(cs.sid).note = TypecastChecks.textOf(e.target.value, 600); });
const capComplete = (v) => !!v && v.capacity != null && !!v.source;
function renderCapNote(rec) {
  const v = rec.verified;
  $('siteCapNote').textContent = capComplete(v) ? 'Counted as a capacity reported by you, with your stated source. Typecast did not verify it.'
    : v ? 'Kept as your note, but not counted as verified until both a number and its source are entered.'
    : 'Shown beside the request in the brief. Typecast never calculates capacity from floor area, photos, listings or parking.';
}
function setVerified() {
  const cs = curSite(); if (!cs) return; S.rev++;
  const cap = TypecastChecks.countOf($('siteCap').value), src = TypecastChecks.textOf($('siteCapSrc').value, 80), rec = siteRec(cs.sid, cs.pid);
  rec.verified = cap == null && !src ? null : { capacity: cap, source: src };       // incomplete input is kept, and only a complete pair counts as verified
  renderCapNote(rec);
}
$('siteCap').addEventListener('input', setVerified); $('siteCapSrc').addEventListener('input', setVerified);
function renderBriefFields() {
  $('briefReviewer').value = S.brief.reviewer; $('briefDate').value = S.brief.date; $('briefNotes').value = S.brief.notes;
}
$('briefReviewer').addEventListener('input', (e) => { S.rev++; S.brief.reviewer = TypecastChecks.textOf(e.target.value, 40); });
$('briefDate').addEventListener('input', (e) => { S.rev++; S.brief.date = TypecastChecks.textOf(e.target.value, 20); });
$('briefNotes').addEventListener('input', (e) => { S.rev++; S.brief.notes = TypecastChecks.textOf(e.target.value, 600); });

// ---- project file: additive community fields (see docs/team/CONTRACT-CHANGES.md) ----
function communityExport() {
  if (S.mode !== 'community') return {};
  const needs = [], sites = [];
  for (const s of S.scenes) {
    const n = S.comm[`need:${s.id}`]; if (n && (n.requested != null || n.note)) needs.push({ scene_id: s.id, requested_count: n.requested, note: n.note });
  }
  for (const key of Object.keys(S.comm)) {
    if (!key.startsWith('site:')) continue;
    const k = parseSiteKey(key), r = S.comm[key];
    if (!k || !S.scenes.some((s) => s.id === k.sid) || !k.pid || sites.length >= 48) continue;
    const sid = k.sid, pid = k.pid;
    const checks = {};
    for (const c of TypecastChecks.COMMUNITY_CHECKS) { const x = r.checks[c.key]; if (x && TypecastChecks.isState(x.state) && (x.state !== 'unknown' || x.note)) checks[c.key] = { state: x.state, note: TypecastChecks.textOf(x.note, 200) }; }
    const tasks = r.tasks.filter((t) => t.text).slice(0, 6).map((t) => ({ text: t.text, owner: t.owner || '' }));
    if (Object.keys(checks).length || r.verified || tasks.length) sites.push({ scene_id: sid, property_id: pid, checks, verified: r.verified ? { capacity: r.verified.capacity, source: r.verified.source } : null, tasks });
  }
  return { mode: 'community', brief: { reviewer: S.brief.reviewer, date: S.brief.date, notes: S.brief.notes }, needs, sites };
}
function communityRestore(restored) {
  S.comm = Object.create(null); S.brief = restored.brief ? { ...restored.brief } : { reviewer: '', date: '', notes: '' };
  for (const n of restored.needs) { const r = needRec(n.scene_id); r.requested = n.requested_count; r.note = n.note; }
  for (const x of restored.sites) {
    const r = siteRec(x.scene_id, x.property_id);
    for (const [k, c] of Object.entries(x.checks)) r.checks[k] = { state: c.state, note: c.note, stale: c.state === 'ok' };      // restored "OK" must be re-verified
    r.verified = x.verified ? { capacity: x.verified.capacity, source: x.verified.source } : null; r.tasks = x.tasks.map((t) => ({ ...t }));
  }
}
const orphanSites = () => Object.keys(S.comm).filter((k) => {
  if (!k.startsWith('site:')) return false;
  const p = parseSiteKey(k), sc = p && S.resp?.scenes?.find((s) => s.id === p.sid);
  return !sc || !(sc.candidates || []).some((c) => c.shot?.property_id === p.pid);
}).length;

// ---- Site Brief: the printable export for community mode ----
function briefModel(s, i) {
  const a = assignFor(s.id); if (!a) return { s, i, a: null };
  const need = S.comm[`need:${s.id}`] || { requested: null, note: '' }, rec = S.comm[siteKey(s.id, a.property_id)] || { checks: {}, verified: null, tasks: [] };
  const fit = fitFor(s.id), counts = TypecastChecks.communityCounts(rec), summary = evidenceSummary(s.id);
  const cand = (S.resp?.scenes?.find((x) => x.id === s.id)?.candidates || []);
  const alts = altChoices(s.id).map((c) => ({ pid: safeId(c.shot.property_id), sim: typeof c.shot.score === 'number' ? c.shot.score.toFixed(2) : 'unknown',
    avail: ['available', 'not_available'].includes(c.property?.availability_status) ? c.property.availability_status : 'unknown' }));
  const items = [];
  for (const c of TypecastChecks.COMMUNITY_CHECKS) {
    const x = rec.checks[c.key] || { state: 'unknown', note: '' };
    if (x.state === 'unknown') items.push(`Establish: ${c.label}.`); else if (x.state === 'issue') items.push(`Resolve: ${c.label}${x.note ? ` (${x.note})` : ''}.`);
    else items.push(`Re-verify before relying on it: ${c.label} (reported OK by the coordinator${x.stale ? ', restored from a file' : ''}).`);
  }
  for (const r of fit.rows) if (r.kind === 'conflict') items.push(`Resolve conflict: ${r.label}. ${r.detail}`); else if (r.kind === 'unknown') items.push(`Establish: ${r.label}. ${r.detail}`);
  items.push('Get the owner\'s permission and agree access before any use.', 'Inspect the site in person; the frame is an indexed scan image, not a current photo.');
  return { s, i, a, need, rec, fit, counts, summary, alts, items, cand: cand.length };
}
async function exportBrief() {
  const p = plan(); if (!p) return status('Find candidate sites first.', true);
  const models = S.scenes.map((s, i) => briefModel(s, i)), snapshot = { at: new Date().toISOString(), mode: S.resp?.mode ?? 'unknown' };
  stopPlay(); $('expPack').disabled = true; status('Building the site brief from real indexed images…');
  try {
    const doc = document.implementation.createHTMLDocument('Typecast site brief');
    const E = (tag, text, cls) => { const n = doc.createElement(tag); if (text != null) n.textContent = text; if (cls) n.className = cls; return n; };
    const cs = doc.createElement('meta'); cs.setAttribute('charset', 'utf-8');
    const csp = doc.createElement('meta'); csp.setAttribute('http-equiv', 'Content-Security-Policy');
    csp.setAttribute('content', "default-src 'none'; img-src data:; style-src 'unsafe-inline'");
    const st = doc.createElement('style'); st.textContent = PACK_CSS; doc.head.prepend(cs, csp); doc.head.append(st);
    const ul = (items) => { const u = E('ul'); items.forEach((x) => u.append(E('li', x))); return u; };
    const totalUnknown = models.filter((m) => m.a).reduce((n, m) => n + m.counts.unknown, 0);
    doc.body.append(E('h1', 'Typecast site brief · preparedness planning'),
      E('p', 'Candidate-site review for volunteer and supply coordination planning. This is a prototype planning aid. It is not an approval of any site, not an emergency or evacuation plan, and nothing was sent to anyone.', 'unk'),
      E('p', `NEEDS VERIFICATION · ${totalUnknown} coordinator check${totalUnknown === 1 ? '' : 's'} still unknown across the selected sites.`, 'strong'),
      E('p', `Generated ${snapshot.at} · source data ${snapshot.mode}${S.brief.reviewer ? ` · Reviewer: ${S.brief.reviewer}` : ''}${S.brief.date ? ` · Review date: ${S.brief.date}` : ''}`, 'meta'));
    if (S.brief.notes) doc.body.append(E('p', `Brief notes: ${S.brief.notes}`));
    for (const m of models) {
      const sec = E('section', null, 'scene');
      sec.append(E('h2', `${m.i + 1}. ${m.s.heading}`), E('p', m.s.description || '(no description)'));
      if (!m.a) { sec.append(E('p', 'No candidate site is assigned to this need in the current plan.', 'unk')); doc.body.append(sec); continue; }
      sec.append(E('p', `Requested participants or volunteers: ${m.need.requested == null ? 'not entered' : m.need.requested}. This is a request, not a capacity.`));
      sec.append(E('h3', 'Selected candidate site'), E('p', `Property ${safeId(m.a.property_id)}, frame ${safeId(m.a.shot_id)}${m.a.swapped ? ' (chosen by hand from the candidate pool)' : ''}. ${m.cand} candidate frame${m.cand === 1 ? '' : 's'} in the pool for this need.`));
      try {
        const url = await dataUrl(`/image/${encodeURIComponent(m.a.shot_id)}`), img = E('img'); img.src = url; img.alt = `Indexed frame of the candidate site for need ${m.i + 1}`;
        sec.append(img, E('p', 'Indexed scan image from the source index. It is not a current photo of the site.', 'meta'));
      } catch (e) { sec.append(E('p', `Indexed image unavailable: ${e.message}`, 'unk')); }
      sec.append(E('h4', 'Source-reported facts (unknown stays unknown)'), doc.importNode(evidenceBrief(m.summary), true));
      const sheet = E('div', null, 'sheet');
      sheet.append(E('h3', 'Requested count and capacity'),
        E('p', `Requested: ${m.need.requested == null ? 'not entered' : m.need.requested} participants or volunteers (a request).`),
        E('p', capComplete(m.rec.verified) ? `Independently verified capacity: ${m.rec.verified.capacity}, as reported by the coordinator. Source given: ${m.rec.verified.source}. Typecast did not verify this.` : 'Independently verified capacity: none provided. Typecast does not calculate capacity from floor area, photos, listings or parking.'),
        ...(m.rec.verified && !capComplete(m.rec.verified) ? [E('p', m.rec.verified.capacity != null ? `A capacity figure (${m.rec.verified.capacity}) was entered without a source, so it is not counted as verified.` : 'A capacity source note was entered without a number, so no capacity is recorded.', 'unk')] : []),
        E('h4', 'Fit evidence (sources, not a score; only simple wording in your needs is read)'), ul(m.fit.rows.map((r) => `${TypecastChecks.KIND_LABEL[r.kind]}: ${r.label}. ${r.detail}${r.source ? ` Source: ${r.source}.` : ''}`)),
        E('h4', 'Coordinator checks (reported by the coordinator, not verified by Typecast)'),
        ul(TypecastChecks.COMMUNITY_CHECKS.map((c) => { const x = m.rec.checks[c.key] || { state: 'unknown', note: '' }; return `${c.label}: ${TypecastChecks.CHECK_STATE_LABEL[x.state]}${x.state === 'ok' && x.stale ? ' (restored from a file; re-verify)' : ''}${x.note ? ` — ${x.note}` : ''}`; })),
        E('h4', 'Follow-ups'), m.rec.tasks.filter((t) => t.text).length ? ul(m.rec.tasks.filter((t) => t.text).map((t) => `${t.text}${t.owner ? ` (${t.owner})` : ''}`)) : E('p', '(none entered)', 'meta'),
        E('h4', 'Notes'), E('p', m.need.note || '(none entered)', m.need.note ? '' : 'meta'),
        E('h4', 'Other candidate sites in the pool (not assessed)'), m.alts.length ? ul(m.alts.map((x) => `Property ${x.pid} · image similarity ${x.sim} · listing ${x.avail}`)) : E('p', 'No other eligible candidate in the pool.', 'meta'),
        E('h4', 'Verification checklist'), ul(m.items));
      sec.append(sheet, doc.importNode(evidenceNodes(m.s.id, m.summary, false), true)); doc.body.append(sec);
    }
    const orphan = orphanSites();
    if (orphan) doc.body.append(E('p', `${orphan} saved site record${orphan === 1 ? '' : 's'} belong to properties no longer in the candidate pool; they are kept in the Project JSON and not shown here.`, 'meta'));
    download(new Blob([`<!doctype html>\n${doc.documentElement.outerHTML}`], { type: 'text/html' }), 'typecast-site-brief.html');
    status('Site brief downloaded. Open it and use Print to save a PDF. It is a planning aid, not an approval.');
  } catch (e) { status(`Site brief export failed: ${e.message}`, true); } finally { $('expPack').disabled = !plan(); }
}

// ================= local draft recovery (per mode, this browser only) =================
// Stores the script, the constraints and a validated project snapshot (takes, notes, coordinator reports, identifiers).
// Never images, keys, provider responses or source rows. Restoring always rebuilds evidence from the current pool through the
// same validation as a file import, so a draft can never bring back availability or safety claims, and stale frames become
// review drafts. Autosave is held while a saved draft is not reflected on screen, so it cannot overwrite a good draft.
const DRAFT_V = 1, DRAFT_MAX = 300000, DRAFT_OPT = 'typecast.director.draft.optout';
const draftKey = (m) => `typecast.director.draft.v${DRAFT_V}.${m}`;
const draftState = { ready: false, hold: { film: false, community: false }, last: '', failed: false, unavailable: false };
const unreadKey = (m) => `${draftKey(m)}.unreadable`, UNREAD_MAX = 400000;
function lstore() { try { return window.localStorage || null; } catch { return null; } }
function lget(k) { try { return lstore()?.getItem(k) ?? null; } catch { return null; } }
function ldel(k) { try { lstore()?.removeItem(k); } catch { /* storage may be blocked */ } }
const draftOn = () => !!lstore() && lget(DRAFT_OPT) !== '1';
function draftEnvelope() {
  const pristine = !S.resp && ($('script').value === (S.mode === 'film' ? DEMO : ''));
  if (pristine && !Object.keys(S.comm).length) return null;                                  // nothing of the user's to keep
  const c = constraints();
  return { v: DRAFT_V, mode: S.mode, script: $('script').value.slice(0, TypecastChecks.LIMITS.chars),
    constraints: { maxLoc: c.max_locations, trucks: c.trucks, cars: c.cars, reqAvail: c.require_available },
    plan_script: S.resp && S.scenes.length ? S.builtScript : null,
    project: S.resp && S.scenes.length ? draftProject() : null };
}
// The saved project keeps only what is needed to rebuild: scene text, takes, notes, reports and frame identifiers. Source facts are re-fetched.
function draftProject() {
  const p = exportSnapshot();
  return { app: p.app, variant: p.variant, ...(p.mode ? { mode: p.mode, brief: p.brief, needs: p.needs, sites: p.sites } : {}),
    scenes: p.scenes.map(({ id, heading, description, variants, location_choice, notes, evidence, decision }) => ({ id, heading, description, evidence: evidence?.frame ? { frame: { shot_id: evidence.frame.shot_id, property_id: evidence.frame.property_id } } : null,
      variants, ...(location_choice ? { location_choice } : {}), ...(notes ? { notes } : {}), ...(decision ? { decision } : {}) })) };
}
function saveDraft() {
  if (!draftState.ready || draftState.hold[S.mode] || S.planBusy || !draftOn()) return false;
  const env = draftEnvelope();
  if (!env) return false;
  const body = JSON.stringify(env);
  if (body === draftState.last) return false;
  if (body.length > DRAFT_MAX) { if (!draftState.failed) { draftState.failed = true; status('Local draft not saved: the project is too large to keep in this browser. Export Project JSON instead.', true); } return false; }
  try {
    lstore().setItem(draftKey(S.mode), JSON.stringify({ ...env, saved_at: new Date().toISOString() }));
    draftState.last = body; draftState.failed = false; return true;
  } catch {
    if (!draftState.failed) { draftState.failed = true; status('Local draft could not be saved (browser storage is full or blocked). Your work is still open; export Project JSON to keep it.', true); }
    return false;
  }
}
function showDraftNotice(msg, buttons = []) {
  const n = $('draftNotice'); n.replaceChildren();
  if (!msg) { n.hidden = true; return; }
  n.append(el('p', { text: msg }), el('div', { class: 'row' }, ...buttons)); n.hidden = false;
}
function draftButton(text, fn, primary) { const b = el('button', { type: 'button', text, ...(primary ? { class: 'primary' } : {}) }); b.addEventListener('click', fn); return b; }
function discardDraft(m = S.mode) { ldel(draftKey(m)); ldel(unreadKey(m)); draftState.hold[m] = false; draftState.last = ''; }
function readDraft(m) {
  const raw = lget(draftKey(m));
  if (raw == null) return null;
  // Unreadable or newer-version drafts are never wiped: one bounded copy is set aside (per mode) with download and discard buttons.
  const bad = (why) => {
    let kept = false;
    if (typeof raw === 'string' && raw.length <= UNREAD_MAX) { try { lstore().setItem(unreadKey(m), raw); kept = true; } catch { kept = false; } }
    if (kept) ldel(draftKey(m)); else draftState.hold[m] = true;            // could not set it aside: leave it and pause autosave so it is not overwritten
    const copy = () => { const t = lget(kept ? unreadKey(m) : draftKey(m)); if (t != null) download(new Blob([t], { type: 'text/plain' }), `typecast-unreadable-draft-${m}.txt`); };
    showDraftNotice(`A saved local draft could not be read (${why}). ${kept ? 'A copy was set aside so nothing is lost.' : 'It was left in place and autosave for this mode is paused so it is not overwritten.'} Nothing else was changed.`,
      [draftButton('Download copy', copy), draftButton('Discard it', () => { ldel(unreadKey(m)); ldel(draftKey(m)); draftState.hold[m] = false; showDraftNotice(''); status('The unreadable draft was discarded.'); })]);
    return null;
  };
  if (typeof raw !== 'string' || raw.length > DRAFT_MAX * 1.2) return bad('too large');
  let d; try { d = JSON.parse(raw); } catch { return bad('not valid data'); }
  if (!d || typeof d !== 'object' || Array.isArray(d) || d.v !== DRAFT_V || d.mode !== m) return bad('unknown version or mode');
  if (typeof d.script !== 'string' || d.script.length > TypecastChecks.LIMITS.chars) return bad('bad script');
  const c = d.constraints; if (!c || typeof c !== 'object') return bad('bad constraints');
  if (d.plan_script != null && (typeof d.plan_script !== 'string' || d.plan_script.length > TypecastChecks.LIMITS.chars)) return bad('bad plan text');
  let projectText = null;
  if (d.project != null) {
    try { projectText = JSON.stringify(d.project); const p = TypecastProject.normalizeProject(projectText); if ((p.mode || 'film') !== m) throw new Error('mode'); } catch { return bad('invalid project'); }
  }
  return { d, projectText, savedAt: typeof d.saved_at === 'string' ? d.saved_at.slice(0, 40) : '' };
}
async function restoreDraft(m = S.mode) {
  if (!lstore() || !draftOn()) return false;
  const r = readDraft(m);
  if (!r) return false;
  draftState.hold[m] = true;                                              // a saved draft exists that the screen does not reflect yet
  const c = r.d.constraints, clampN = (v, lo, hi, d0) => { const n = Math.floor(Number(v)); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : d0; };
  $('script').value = r.d.script; $('maxLoc').value = String(clampN(c.maxLoc, 1, 4, 3)); $('trucks').value = String(clampN(c.trucks, 0, 20, 0));
  $('cars').value = String(clampN(c.cars, 0, 50, 0)); $('reqAvail').checked = c.reqAvail === true; renderParse();
  const when = r.savedAt ? ` from ${new Date(r.savedAt).toLocaleString()}` : '';
  const buttons = (retry) => [...(retry ? [draftButton('Retry rebuilding evidence', () => restoreDraft(m), true)] : []),
    draftButton('Discard this draft', () => { discardDraft(m); if (S.mode === m) { applyModeState(freshMode(m)); applyModeUI(); renderAll(); renderParse(); } showDraftNotice(''); status('Local draft discarded.'); }),
    draftButton('Stop keeping drafts', () => { try { lstore().setItem(DRAFT_OPT, '1'); } catch { /* ignore */ } for (const x of ['film', 'community']) { ldel(draftKey(x)); ldel(unreadKey(x)); draftState.hold[x] = false; } $('draftOpt').checked = false; showDraftNotice(''); status('Local drafts are off and saved drafts were removed.'); })];
  if (!r.projectText) { draftState.hold[m] = false; showDraftNotice(`Restored your local draft${when} (this browser only): your text and settings. No plan had been built.`, buttons(false)); return true; }
  const file = { size: r.projectText.length, text: async () => r.projectText };
  const ok = await importProject(file);                                    // a structured result, not a status string
  if (ok) {
    $('script').value = r.d.script; renderParse();                      // keep exactly what was typed, not the re-joined scene lines
    S.builtScript = typeof r.d.plan_script === 'string' ? r.d.plan_script : r.d.script;
    const changed = typeof r.d.plan_script === 'string' && r.d.plan_script !== r.d.script;
    draftState.hold[m] = false; draftState.last = ''; showDraftNotice(`Restored your local draft${when} (this browser only). Evidence was rebuilt from the current data; frames that no longer match are kept for review, and anything you marked OK still needs re-verifying.${changed ? ' Your script changed after the last plan was built, so the plan shown is for the earlier text. Press Build to refresh it.' : ''}`, buttons(false));
  } else showDraftNotice(`Restored the text of your local draft${when}, but its plan could not be rebuilt yet. The saved draft is kept and autosave is paused so it cannot be overwritten.`, buttons(true));
  return ok;
}
async function initDraft() {
  const note = $('draftNote');
  if (!lstore()) { draftState.unavailable = true; note.textContent = 'Local drafts are unavailable in this browser, so your work is not being kept. Export Project JSON to save it.'; $('draftOpt').disabled = true; $('draftClear').disabled = true; return; }
  $('draftOpt').checked = draftOn();
  note.textContent = 'Kept only in this browser, as readable text in its local storage: your script, notes, takes or coordinator reports, and identifiers. It never holds images, keys or provider data. It is not encrypted or synced; clear it on a shared computer. With several tabs open, the last one to save wins.';
  try { await restoreDraft('film'); } finally { draftState.ready = true; }
}
$('draftOpt').addEventListener('change', (e) => {
  if (e.target.checked) { try { lstore().removeItem(DRAFT_OPT); } catch { /* ignore */ } status('Local drafts are on for this browser.'); }
  else { try { lstore().setItem(DRAFT_OPT, '1'); } catch { /* ignore */ } for (const x of ['film', 'community']) { ldel(draftKey(x)); ldel(unreadKey(x)); draftState.hold[x] = false; } draftState.last = ''; showDraftNotice(''); status('Local drafts are off and saved drafts were removed.'); }
});
$('draftClear').addEventListener('click', () => {
  ldel(draftKey(S.mode)); ldel(unreadKey(S.mode)); draftState.hold[S.mode] = false; showDraftNotice('');
  const env = draftEnvelope(); draftState.last = env ? JSON.stringify(env) : '';          // a literal clear: the open work is not saved again until you change something
  status(`Saved ${S.mode === 'community' ? 'community' : 'film'} draft cleared. Your open work is unchanged. It will be saved again when you next change something.`);
});
if (typeof setInterval === 'function') setInterval(saveDraft, 1500);
if (typeof document.addEventListener === 'function') document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') saveDraft(); });
window.addEventListener('pagehide', () => { saveDraft(); });

window.typecastPlanningSnapshot = () => ({ plan: plan(), response: S.resp, mode:S.mode, limits:{maxLocations:$('maxLoc').value,trucks:$('trucks').value,cars:$('cars').value,requireAvailable:$('reqAvail').checked}, scenes:S.scenes.map(s=>({id:s.id,heading:s.heading})), rejected:[...S.forbidden], selectedScene: S.sceneId, selectedShot: assignFor(S.sceneId)?.shot_id, assignments: S.scenes.map(s => assignFor(s.id)).filter(Boolean), sceneCount: S.scenes.length,
  stale: anySwap() || (S.resp && (S.builtScript !== $('script').value || (PLANNING_REQUESTS.has(S.resp) && PLANNING_REQUESTS.get(S.resp) !== JSON.stringify(constraints())))) });
$('script').value = DEMO;
renderAll(); renderParse(); applyModeUI();
// Canvas text uses the app's faces once they load; until then the system fallback draws.
if (document.fonts?.load) {
  Promise.all(['600 21px Barlow', '500 19px Barlow', '500 30px Barlow', '600 34px Barlow'].map((f) => document.fonts.load(f)))
    .then(() => { if (!S.play.on) draw(); }).catch(() => {});
}
status('Edit the script, then Build plan. Nothing appears on the stage until the backend returns a plan; check its mode label.');
initDraft();
