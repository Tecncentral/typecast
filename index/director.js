'use strict';
const $ = (id) => document.getElementById(id);
const POSES = ['stand', 'sit', 'walk'];
const ORIGIN_SAMPLE = 'authored-sample', ORIGIN_TAG = 'AUTHORED SAMPLE · not AI';
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
const S = { swaps: {}, transfer: {}, swapUndo: null, notes: {}, built: null, compare: false, rev: 0, scenes: [], resp: null, planIdx: 0, planBusy: false, sceneId: null, variant: 'A', forbidden: [], edits: {},
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
  const base = `${covered}/${S.scenes.length} scenes · ${p.locations} location${p.locations === 1 ? '' : 's'} · ${p.company_moves ?? '?'} move${p.company_moves === 1 ? '' : 's'}`;
  return p === plan() && anySwap() ? `${covered}/${S.scenes.length} scenes · location swapped by hand, totals not recalculated` : base;
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
const anySwap = () => S.scenes.some((s) => validSwap(s.id));
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
  for (const b of $('framePicker').querySelectorAll('button')) b.disabled = on;   // strips rendered mid-build must not stay disabled
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
const MOCK_NOTE = 'MOCK FIXTURE RESULTS: placeholder frames, fixture rankings and fixture statuses, not real rooms, sources or capacity. ';
const modeNote = (data) => (data?.mode === 'mock' ? MOCK_NOTE : '');
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
    orderPlans(data);
    S.scenes = scenes; S.resp = data; S.planIdx = 0; S.frameOverrides = {}; S.swaps = {}; S.swapUndo = null; S.built = { trucks: body.trucks, cars: body.cars, require_available: body.require_available };
    if (!scenes.some((s) => s.id === S.sceneId)) { S.sceneId = scenes[0].id; S.actorIdx = 0; }
    noteFrameChanges(prev); renderAll();
    if (data.plans.length) status(`${modeNote(data)}${data.plans.length} candidate plan(s) returned. Candidates are not verified shootability.`, data.mode === 'mock');
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
  const bw = Math.min(ctx.measureText(BADGE).width, W * 0.56) + 28;
  ctx.fillStyle = INK.scrim; pill(ctx, 18, 18, bw, 40);
  ctx.fillStyle = INK.accent; ctx.fillText(BADGE, 32, 38.5, W * 0.56);
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
  return { imgEl: im && im.ok ? im.el : null, missing, prov: provText(sid, v), shot: a ? viewShot(sid, v) : null, t, editing, sel };
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
// A plain-language brief built only from the sanitized summary; unknowns stay unknown.
function evidenceBrief(a) {
  const ul = el('ul', { class: 'brief' });
  const item = (k, v, unknown = false) => ul.append(el('li', {}, el('b', { text: k }), el('span', { class: unknown ? 'unk' : '', text: v })));
  const num = (v, d = 0) => (typeof v === 'number' ? v.toFixed(d) : null);
  const p = a.property || {}, lg = a.logistics || {}, r = a.room || {};
  const av = p.availability_status;
  item('Listing', av === 'available' ? 'Marketed as available. Not filming permission.'
    : av === 'not_available' ? 'Not marketed as available.' : 'Unknown.', av !== 'available' && av !== 'not_available');
  const building = [num(p.year_built) && `built ${num(p.year_built)}`, num(p.size_sqft) && `${Number(p.size_sqft).toLocaleString('en-US')} sq ft`].filter(Boolean);
  item('Building', building.length ? building.join(' · ') : 'Unknown.', !building.length);
  const room = [num(r.room_area_m2) && `${num(r.room_area_m2)} m² floor`, num(r.ceiling_m, 1) && `ceiling ${num(r.ceiling_m, 1)} m`,
    num(r.depth_m, 1) && `depth ${num(r.depth_m, 1)} m`].filter(Boolean);
  item('Room', room.length ? `${room.join(' · ')} (index estimate)` : 'Unknown. Measure on site.', !room.length);
  if (lg.parking_status === 'unknown') item('Parking', 'Unknown. Not a parking approval.', true);
  else item('Parking', `${num(lg.truck_spaces) ?? '?'} trucks, ${num(lg.car_spaces) ?? '?'} cars, ${lg.parking_status}`
    + (lg.enough_parking === true ? '. Covers the requested vehicles.' : lg.enough_parking === false ? '. Short of the requested vehicles.' : '.'));
  item('Crew walk', lg.walk_status === 'unknown' ? 'Unknown.' : `${num(lg.walk_m) ?? '?'} m, ${lg.walk_status}.`, lg.walk_status === 'unknown');
  item('Noise', lg.noise_status === 'unknown' ? 'Unknown.' : `Proximity screen, ${lg.noise_status}. Not a sound measurement.`, lg.noise_status === 'unknown');
  return ul;
}
function evidenceNodes(sid, summary = evidenceSummary(sid), collapsible = true) {
  const f = document.createDocumentFragment(), a = summary;
  if (!a) { f.append(el('p', { class: 'unk', text: S.resp ? 'Uncovered in this plan: no location assigned.' : 'No plan yet.' })); return f; }
  const fields = [kv('Frame · Matterport index', a.frame),
    kv('Room metrics · index estimate, not calibrated to stage', a.room),
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
      el('span', { class: a ? 'loc' : 'loc none', text: a ? `Location ${locLetter(a.property_id)}${a.swapped ? ' · swapped' : a.manual_frame ? ' · your frame' : ''}${(continuityMap()[s.id] || []).some((c) => c.level !== 'unknown') ? ' · continuity note' : ''}` : S.resp ? 'Uncovered: no location' : 'Not planned yet' })); }));
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
  const label = el('label', { text: `Frames in this location (creative choice) · ${choices.length}` }), select = el('select', { 'aria-label': 'Frame within assigned property' });
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
  const box = el('details', { class: 'alt-locs' }, el('summary', { text: `Try another location (${choices.length})` }));
  if (!choices.length) { box.append(el('p', { class: 'meta', text: 'No other eligible location is in this plan\'s candidate pool. Reject or change constraints, then rebuild, to widen it.' })); return box; }
  box.append(el('p', { class: 'meta', text: 'One click swaps this scene to that location and carries your staging over as a draft to review. The plan summary is not recalculated.' }));
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
  }
  renderAll();
  status(`Scene ${sceneNumber(sid)} now uses ${safeId(c.shot.property_id)}. Your staging came along as a draft: review it on this frame.`);
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
  if (!sw) { n.hidden = true; return; }
  const unreviewed = !!(t && !t.reviewed);
  const row = el('div', { class: 'row' });
  if (unreviewed) {
    const ok = el('button', { type: 'button', class: 'primary', text: 'Staging looks right on this frame' });
    ok.addEventListener('click', () => { S.rev++; t.reviewed = true; renderAll(); status('Marked reviewed on this exact frame. Positions are still uncalibrated screen space.'); });
    row.append(ok);
  }
  if (S.swapUndo && S.swapUndo.sid === sid) { const u = el('button', { type: 'button', text: 'Undo swap' }); u.addEventListener('click', undoSwap); row.append(u); }
  const back = el('button', { type: 'button', text: 'Back to planned location' }); back.addEventListener('click', backToPlanned); row.append(back);
  n.append(el('p', { text: `Location swapped for scene ${sceneNumber(sid)}: ${safeId(sw.from_property_id)} → ${safeId(sw.property_id)}. ${unreviewed
    ? 'Your takes, durations, dialogue and stand-ins were carried over as a draft. They were NOT verified against this frame and the previous scan identity does not apply. Fit stays uncalibrated until you confirm.'
    : 'The plan summary and company moves were not recalculated for this choice.'}` }), row);
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
  return TypecastChecks.fitCheck({ scene: s, cand: a ? candFor(sid, a.shot_id) : null, built: S.built, mode: S.resp?.mode });
}
function checkRow(r) {
  return el('li', { class: `chk chk-${r.kind}` }, el('b', { text: `${TypecastChecks.KIND_LABEL[r.kind] || 'Note'}: ` }), el('span', { text: `${r.label}. ${r.detail}` }),
    r.source ? el('small', { text: ` Source: ${r.source}.` }) : '');
}
function renderChecks() {
  const box = $('sceneChecks'), sid = S.sceneId, a = assignFor(sid);
  if (!window.TypecastChecks || !a) { box.hidden = true; return; }
  const fit = fitFor(sid), cont = (continuityMap()[sid] || []), real = cont.filter((c) => c.level !== 'unknown');
  const body = $('checksBody'); body.replaceChildren();
  $('checksSummary').textContent = `Fit check · ${TypecastChecks.fitSummaryText(fit)}${real.length ? ` · ${real.length} continuity note${real.length === 1 ? '' : 's'}` : ''}`;
  body.append(el('p', { class: 'meta', text: 'Only fields the sources supplied are compared. Unknown stays unknown, and image similarity is not a fit score.' }),
    el('ul', { class: 'chk-list' }, ...fit.rows.map(checkRow)));
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
  renderPlan(); renderRail(); renderTimeline(); renderInspector(); renderFrameNotice(); renderFrames(); renderStageHead(); renderCompareStrip(); renderSwapNotice(); renderChecks(); renderNotes();
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
  S.rev++; const ed = S.edits[S.pending.k]; S.undo = { k: S.pending.k, prev: clone(ed.B) }; ed.B = clone(S.pending.shot);
  clearPending(); $('undo').disabled = false; stopPlay(); renderAll();
  status(`${sample ? 'Applied the authored sample to variant B' : 'Applied to variant B'}${S.variant === 'B' || S.compare ? '.' : '. Switch to B to view it.'}`);
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
const PACK_PRINT = '@media print{body{max-width:none;margin:0;font-size:11pt}section.scene{break-inside:avoid-page;page-break-inside:avoid}img{max-height:9cm;width:auto;max-width:100%}.sheet li{list-style:none}.sheet li:before{content:"\\2610 "}h1,h2,h3{break-after:avoid}}.sheet{border:1px solid #c98a1c;padding:.6rem .9rem;margin:.8rem 0;background:#fbf6ec}.sheet h3{margin:.2rem 0 .4rem}.sheet ul{padding-left:1.1rem}.sheet .k{font-weight:bold}';
const PACK_CSS = 'body{font:14px/1.5 Georgia,serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a120c}section.scene{break-inside:avoid;border-top:2px solid #c98a1c;padding:1rem 0}img{width:100%;border:1px solid #ccc}.meta{color:#6b5847;font-size:12px}dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:12px}dt{color:#6b5847}dd{margin:0}.unk{color:#b3261e;font-style:italic}.warn{font-size:12px}h4{margin:.6rem 0 .2rem}' + PACK_PRINT;
// Safe, validated per-scene production state that Project JSON carries (identifiers and bounded text only).
function sceneProduction(sid) {
  const out = {}, sw = validSwap(sid), t = S.transfer[keyOf(sid)], n = S.notes[sid];
  if (sw) out.location_choice = { shot_id: safeId(sw.shot_id), property_id: safeId(sw.property_id), from_shot_id: safeId(sw.from_shot_id), from_property_id: safeId(sw.from_property_id), staging_reviewed: !(t && !t.reviewed) };
  if (n && (n.dressing || n.group)) out.notes = { dressing: cleanText(n.dressing, 600), group: cleanText(n.group, 12) };
  return out;
}
function exportSnapshot() {
  const p = plan();
  return clone({ app: 'Typecast Director', exported_at: new Date().toISOString(), variant: S.variant, plan_index: S.planIdx,
    honesty: 'Candidate plans only. Uncalibrated screen-space rehearsal; geometric fit unknown. Plan score describes original solver frames; manual frame choices retain the assigned property.',
    source_mode: S.resp?.mode ?? 'unknown', locations: anySwap() ? null : count(p?.locations), company_moves: anySwap() ? null : p?.company_moves ?? null, mean_similarity: anySwap() ? null : p?.mean_similarity ?? null,
    plan_note: anySwap() ? 'A location was swapped by hand; plan locations, moves and similarity were not recalculated.' : undefined,
    review_needed: S.importReview,
    scenes: S.scenes.map((s) => ({ ...s, ...sceneProduction(s.id), evidence: evidenceSummary(s.id),
      manual_frame: !!assignFor(s.id)?.manual_frame, staging: assignFor(s.id) ? sanitizeShot(shotData(s.id), true) : null,
      variants: assignFor(s.id) ? { A: sanitizeShot(shotData(s.id, 'A'), true), B: sanitizeShot(shotData(s.id, 'B'), true) } : null,
      provenance_label: provText(s.id) })) });
}
function decisionFor(sid) {
  const a = assignFor(sid); if (!a || !window.TypecastChecks) return null;
  const fit = fitFor(sid), cont = continuityMap()[sid] || [], sw = validSwap(sid), t = S.transfer[keyOf(sid)];
  const take = (v) => sanitizeShot(shotData(sid, v), true);
  return { number: sceneNumber(sid), property: safeId(a.property_id), shot: safeId(a.shot_id), swap: sw ? { from: safeId(sw.from_property_id) } : null,
    carried: !!(t && !t.reviewed), takes: { A: take('A'), B: take('B') }, fit, cont, notes: S.notes[sid] || null,
    checklist: TypecastChecks.checklist(fit, cont, { carried: !!(t && !t.reviewed) }) };
}
function decisionNodes(E, d, activeVariant) {
  const box = E('div', null, 'sheet');
  box.append(E('h3', `Production decision sheet · scene ${d.number}`),
    E('p', 'This sheet records choices and open questions. It contains no prices, permissions, owner contact or confirmation that a set is feasible.', 'meta'));
  box.append(E('h4', 'Location choice'), E('p', `Property ${d.property}, frame ${d.shot}.${d.swap ? ` Chosen by hand from the candidate pool instead of ${d.swap.from}; plan totals were not recalculated.` : ' As selected by the plan or your frame choice.'}`));
  if (d.carried) box.append(E('p', 'Staging was carried over from another frame and has NOT been reviewed on this one. Positions are uncalibrated screen space.', 'unk'));
  box.append(E('h4', 'Takes (both listed; the image above shows take ' + activeVariant + ')'));
  for (const v of ['A', 'B']) {
    const t = d.takes[v];
    box.append(E('p', `Take ${v}: ${t.duration_sec}s, ${t.actors.length} stand-in${t.actors.length === 1 ? '' : 's'}${t.dialogue ? `, line: ${t.dialogue}` : ', no dialogue'}${t.origin ? ' · AUTHORED SAMPLE (pre-written, not AI-generated)' : ''}.`, 'meta'));
  }
  const ul = (items) => { const u = E('ul'); items.forEach((i) => u.append(E('li', i))); return u; };
  box.append(E('h4', 'Fit evidence (sources, not a score)'), ul(d.fit.rows.map((r) => `${TypecastChecks.KIND_LABEL[r.kind]}: ${r.label}. ${r.detail}${r.source ? ` Source: ${r.source}.` : ''}`)));
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
          const staged = E('img'), raw = E('img');
          staged.src = cv.toDataURL('image/jpeg', 0.88); staged.alt = `Staged rehearsal frame, scene ${i + 1}`;
          raw.src = url; raw.alt = `Indexed source frame ${a.shot_id}`;
          sec.append(E('h4', 'Staged frame (uncalibrated screen space)'), staged, E('h4', 'Indexed source frame'), raw);
        } catch (e) { sec.append(E('p', `Indexed image unavailable: ${e.message}`, 'unk')); }
        sec.append(E('h4', `Variant ${snapshot.variant} · ${sh.duration_sec}s`), E('p', sh.dialogue || '(no dialogue)'));
        if (sh.origin) sec.append(E('p', 'This take is derived from an AUTHORED SAMPLE: pre-written blocking, not AI-generated, not an interpretation of any instruction.', 'unk'));
        if (sheets[i]) sec.append(decisionNodes(E, sheets[i], snapshot.variant));
        sh.actors.forEach((ac) => sec.append(E('p', `${ac.name} (${ac.pose}, scale ${ac.scale}): (${ac.x0.toFixed(2)}, ${ac.y0.toFixed(2)}) → (${ac.x1.toFixed(2)}, ${ac.y1.toFixed(2)})`, 'meta')));
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
    orderPlans(data);
    // Newer user work must never be silently overwritten by a slow import.
    if (S.rev !== rev || $('script').value !== scriptAtStart)
      throw new Error('you changed the script or staging while the project was loading, so nothing was replaced. Import again when ready');
    if (JSON.stringify(constraints()) !== JSON.stringify(limits))
      throw new Error('location or vehicle constraints changed while evidence was loading, so the result would not match the visible controls. Import again');
    const restored = TypecastProject.restoreEdits(project, data);
    // Commit only after validation and retrieval succeed. Imported evidence never becomes source truth.
    Object.assign(S, { scenes, resp: data, planIdx: 0, sceneId: scenes[0].id, actorIdx: 0,
      edits: restored.edits, frameOverrides: restored.frameOverrides, importReview: restored.reviewNeeded,
      swaps: restored.swaps, transfer: restored.transfers, notes: restored.notes, swapUndo: null, built: { trucks: limits.trucks, cars: limits.cars, require_available: limits.require_available },
      frameChange: {}, forbidden: [], undo: null, variant: project.variant });
    $('undo').disabled = true;
    $('script').value = scenes.map((scene) => `${scene.heading} | ${scene.description}`.replace(/[\r\n]+/g, ' ')).join('\n');
    $('varA').setAttribute('aria-pressed', String(S.variant === 'A'));
    $('varB').setAttribute('aria-pressed', String(S.variant === 'B'));
    renderAll();
    status(`${modeNote(data)}Project loaded with fresh evidence. ${restored.restored} scene draft(s) restored to exact saved frames; ${restored.reviewNeeded.length} retained for review.`, !!restored.reviewNeeded.length);
  } catch (e) { status(`Project not loaded; existing work kept: ${e.message}`, true); }
  finally { busy(false); }
}
$('impProject').addEventListener('change', (event) => importProject(event.target.files[0]));

// ---------- events ----------
$('build').addEventListener('click', () => build(false));
$('script').addEventListener('input', () => { S.rev++; });
$('demo').addEventListener('click', () => { S.rev++; $('script').value = DEMO; status('Demo script loaded. Press Build plan; the plan summary states whether results are live or mock fixtures.'); });
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
  if (S.compare) return;
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
$('expPack').addEventListener('click', exportPack);
$('expReel').addEventListener('click', exportReel);
$('cancelReel').addEventListener('click', () => reelCtrl && reelCtrl.abort());
window.addEventListener('pagehide', () => { if (rec) rec.stop(); if (reelCtrl) reelCtrl.abort(); stopPlay(); });

$('script').value = DEMO;
renderAll();
// Canvas text uses the app's faces once they load; until then the system fallback draws.
if (document.fonts?.load) {
  Promise.all(['600 21px Barlow', '500 19px Barlow', '500 30px Barlow', '600 34px Barlow'].map((f) => document.fonts.load(f)))
    .then(() => { if (!S.play.on) draw(); }).catch(() => {});
}
status('Edit the script, then Build plan. Nothing appears on the stage until the backend returns a plan; check its mode label.');
