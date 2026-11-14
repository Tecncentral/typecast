'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const C = require('../director-checks.js');

const cand = (over = {}) => ({
  shot: { shot_id: 'sh1', property_id: 'p1', score: 0.9, room_area_m2: 60, ceiling_m: 2.6, ...(over.shot || {}) },
  property: { availability_status: null, available: true, ...(over.property || {}) },
  logistics: { parking_status: null, enough_parking: null, noise_flags: [], noise_status: null, ...(over.logistics || {}) },
  warnings: over.warnings || [],
});
const scene = (description = 'A kitchen', heading = 'INT. KITCHEN - DAY') => ({ heading, description });
const kinds = (r) => r.rows.map((x) => x.kind);
const find = (r, label) => r.rows.find((x) => x.label === label);

test('similarity is labelled as such and never becomes a fit score or percentage', () => {
  const r = C.fitCheck({ scene: scene(), cand: cand(), built: { trucks: 0, cars: 0, require_available: false }, mode: 'live' });
  const sim = r.rows[0];
  assert.equal(sim.kind, 'similarity'); assert.match(sim.detail, /not a fact about the room and not a fit score/);
  assert.equal(JSON.stringify(r).includes('%'), false);
  assert.equal(r.similarity, 0.9);
});

test('availability follows the status field only; the legacy boolean never counts', () => {
  const unknown = C.fitCheck({ scene: scene(), cand: cand(), built: { require_available: true } });
  assert.equal(find(unknown, 'Listing availability').kind, 'unknown');           // available:true but status null
  const no = C.fitCheck({ scene: scene(), cand: cand({ property: { availability_status: 'not_available' } }), built: { require_available: true } });
  assert.equal(find(no, 'Listing availability').kind, 'conflict');
  const info = C.fitCheck({ scene: scene(), cand: cand({ property: { availability_status: 'not_available' } }), built: { require_available: false } });
  assert.equal(find(info, 'Listing availability').kind, 'info');
  const yes = C.fitCheck({ scene: scene(), cand: cand({ property: { availability_status: 'available' } }), built: { require_available: true } });
  assert.equal(find(yes, 'Listing availability').kind, 'match'); assert.match(find(yes, 'Listing availability').detail, /not filming permission/);
});

test('vehicles use the source sufficiency flag; unknown capacity is unknown, never a pass', () => {
  const b = { trucks: 2, cars: 3 };
  const P = 'Parking for your vehicles';
  assert.equal(find(C.fitCheck({ scene: scene(), cand: cand(), built: b }), P).kind, 'unknown');
  const unk = C.fitCheck({ scene: scene(), cand: cand({ logistics: { parking_status: 'unknown', enough_parking: true } }), built: b });
  assert.equal(find(unk, P).kind, 'unknown');                                      // flag ignored when status unknown
  assert.equal(find(C.fitCheck({ scene: scene(), cand: cand({ logistics: { parking_status: 'estimated', enough_parking: false } }), built: b }), P).kind, 'conflict');
  assert.equal(find(C.fitCheck({ scene: scene(), cand: cand({ warnings: [{ field: 'parking_capacity', status: 'insufficient' }], logistics: { parking_status: 'estimated' } }), built: b }), P).kind, 'conflict');
  assert.equal(find(C.fitCheck({ scene: scene(), cand: cand({ logistics: { parking_status: 'estimated', enough_parking: true } }), built: b }), P).kind, 'estimate');
  assert.equal(find(C.fitCheck({ scene: scene(), cand: cand({ logistics: { parking_status: 'measured', enough_parking: true } }), built: b }), P).kind, 'match');
  assert.equal(find(C.fitCheck({ scene: scene(), cand: cand(), built: { trucks: 0, cars: 0 } }), P), undefined);
});

test('numbers the user wrote are compared only as lower bounds against index estimates, in commensurate units', () => {
  const ok = C.fitCheck({ scene: scene('open plan, at least 40 m2 of floor'), cand: cand(), built: {} });
  assert.equal(find(ok, 'Floor area').kind, 'estimate'); assert.match(find(ok, 'Floor area').detail, /not site measurements/);
  assert.equal(find(C.fitCheck({ scene: scene('at least 100 m² floor'), cand: cand(), built: {} }), 'Floor area').kind, 'conflict');
  assert.equal(find(C.fitCheck({ scene: scene('at least 1000 sq ft'), cand: cand(), built: {} }), 'Floor area').kind, 'conflict'); // 92.9 m2 > 60
  assert.equal(find(C.fitCheck({ scene: scene('at least 500 sqft'), cand: cand(), built: {} }), 'Floor area').kind, 'estimate');   // 46.5 m2 <= 60
  assert.equal(find(C.fitCheck({ scene: scene('ceilings at least 3 m'), cand: cand(), built: {} }), 'Ceiling height').kind, 'conflict');
  assert.equal(find(C.fitCheck({ scene: scene('at least 8 ft ceilings'), cand: cand(), built: {} }), 'Ceiling height').kind, 'estimate'); // 2.44 m <= 2.6
  assert.equal(find(C.fitCheck({ scene: scene('at least 40 m2'), cand: cand({ shot: { room_area_m2: null } }), built: {} }), 'Floor area').kind, 'unknown');
  // no bound word, or an unrelated number: nothing is compared or invented
  assert.equal(find(C.fitCheck({ scene: scene('a 40 m2 kitchen, 3 sisters, 2 doors'), cand: cand(), built: {} }), 'Floor area'), undefined);
});

test('doors, windows and quiet are never inferred from missing data', () => {
  const r = C.fitCheck({ scene: scene('a door to the garden, big windows, quiet'), cand: cand(), built: {} });
  const d = find(r, 'Details in your script');
  assert.equal(d.kind, 'unknown'); assert.match(d.detail, /door/); assert.match(d.detail, /window/); assert.match(d.detail, /no criterion-level analysis/);
  assert.equal(find(r, 'Quiet').kind, 'unknown');
  const flagged = C.fitCheck({ scene: scene('quiet please'), cand: cand({ logistics: { noise_status: 'estimated', noise_flags: ['highway'] } }), built: {} });
  assert.equal(find(flagged, 'Quiet').kind, 'conflict'); assert.match(find(flagged, 'Quiet').detail, /not a sound measurement/);
  const emptyKnown = C.fitCheck({ scene: scene('quiet please'), cand: cand({ logistics: { noise_status: 'estimated', noise_flags: [] } }), built: {} });
  assert.equal(find(emptyKnown, 'Quiet').kind, 'unknown');                         // empty flags never mean quiet
});

test('no frame yields one unknown row and nothing else', () => {
  const r = C.fitCheck({ scene: scene(), cand: null, built: {} });
  assert.deepEqual(kinds(r), ['unknown']); assert.equal(r.summary.unknowns, 1);
});

test('summary text counts conflicts, unknowns and estimated consistency without any score', () => {
  const r = C.fitCheck({ scene: scene('at least 100 m2'), cand: cand(), built: { require_available: true } });
  const t = C.fitSummaryText(r);
  assert.match(t, /1 conflict · 1 unknown/); assert.equal(/\d%|score/.test(t), false);
});

const sc = (id, number, group, property, shot, heading = 'INT. A - DAY', actors = []) => ({ id, number, heading, group,
  frame: property ? { property_id: property, shot_id: shot } : null, take: property ? { actors } : null });
const actor = (name, x0, y0, x1, y1) => ({ name, x0, y0, x1, y1 });

test('continuity is silent without an explicit link, even across different locations', () => {
  assert.deepEqual(C.continuity([sc('a', 1, '', 'p1', 's1'), sc('b', 2, '', 'p2', 's2')], 'A'), {});
  assert.deepEqual(C.continuity([sc('a', 1, 'X', 'p1', 's1')], 'A'), {});          // a group of one
});

test('linked scenes in different properties are a verified mismatch with a corrective action', () => {
  const m = C.continuity([sc('a', 1, 'X', 'p1', 's1'), sc('b', 2, 'X', 'p2', 's2')], 'A');
  assert.equal(m.a[0].level, 'verified'); assert.match(m.a[0].text, /p1 and p2/); assert.match(m.b[0].action, /Try another location/);
});

test('same property but different frames: positions are unknown, not a numeric discontinuity', () => {
  const m = C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Mara', .1, .1, .9, .9)]), sc('b', 2, 'X', 'p1', 's2', 'INT. A - DAY', [actor('Mara', .1, .1, .1, .1)])], 'A');
  assert.equal(m.a.length, 1); assert.equal(m.a[0].level, 'unknown'); assert.match(m.a[0].text, /cannot be compared/);
});

test('an actor jump is flagged only on the exact same frame, case-insensitively, above the threshold', () => {
  const jump = C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Mara', .2, .8, .8, .8)]), sc('b', 2, 'X', 'p1', 's1', 'INT. A - DAY', [actor('MARA', .2, .8, .2, .8)])], 'A');
  assert.equal(jump.a[0].level, 'potential'); assert.match(jump.a[0].text, /Mara ends scene 1 at \(0\.80, 0\.80\).*starts scene 2 at \(0\.20, 0\.80\)/); assert.match(jump.a[0].action, /Set Mara/);
  const near = C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Mara', .2, .8, .5, .8)]), sc('b', 2, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Mara', .52, .8, .5, .8)])], 'A');
  assert.deepEqual(near, {});
  const other = C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Mara', .2, .8, .8, .8)]), sc('b', 2, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Joe', .2, .8, .2, .8)])], 'A');
  assert.deepEqual(other, {});                                                      // different characters: nothing to compare
});

test('time-of-day differences inside a link are only possible mismatches; unlinked or unparseable stay silent', () => {
  const m = C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A - DAY'), sc('b', 2, 'X', 'p1', 's1', 'INT. A - NIGHT')], 'A');
  assert.equal(m.a.find((i) => /DAY and NIGHT/.test(i.text)).level, 'potential');
  assert.deepEqual(C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A'), sc('b', 2, 'X', 'p1', 's1', 'INT. A - LATER')], 'A'), {});
  assert.equal(C.timeOfDay('INT. KITCHEN - DAY'), 'DAY'); assert.equal(C.timeOfDay('EXT. YARD, NIGHT'), 'NIGHT'); assert.equal(C.timeOfDay('INT. KITCHEN'), null);
});

test('an uncovered linked scene cannot be compared; the checklist only lists unresolved items', () => {
  const m = C.continuity([sc('a', 1, 'X', 'p1', 's1'), sc('b', 2, 'X', null)], 'A');
  assert.equal(m.a[0].level, 'unknown');
  const fit = C.fitCheck({ scene: scene('at least 100 m2'), cand: cand(), built: { require_available: true } });
  const list = C.checklist(fit, [{ level: 'potential', text: 't', action: 'a' }, { level: 'unknown', text: 'skip', action: 'x' }], { carried: true });
  assert.ok(list.some((x) => /^Resolve conflict: Floor area/.test(x))); assert.ok(list.some((x) => /^Establish: Listing availability/.test(x)));
  assert.ok(list.some((x) => /^Continuity \(potential\)/.test(x))); assert.equal(list.some((x) => /skip/.test(x)), false);
  assert.ok(list.some((x) => /Re-stage the carried-over blocking/.test(x))); assert.match(list.at(-1), /Measure the room/);
  assert.equal(list.some((x) => /\$|price|permit|contact/i.test(x)), false);
});
