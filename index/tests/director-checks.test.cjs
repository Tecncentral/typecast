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
const noIssues = (m) => assert.deepEqual(Object.keys(m), []);
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
  noIssues(C.continuity([sc('a', 1, '', 'p1', 's1'), sc('b', 2, '', 'p2', 's2')], 'A'));
  noIssues(C.continuity([sc('a', 1, 'X', 'p1', 's1')], 'A'));          // a group of one
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
  noIssues(near);
  const other = C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Mara', .2, .8, .8, .8)]), sc('b', 2, 'X', 'p1', 's1', 'INT. A - DAY', [actor('Joe', .2, .8, .2, .8)])], 'A');
  noIssues(other);                                                      // different characters: nothing to compare
});

test('time-of-day differences inside a link are only possible mismatches; unlinked or unparseable stay silent', () => {
  const m = C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A - DAY'), sc('b', 2, 'X', 'p1', 's1', 'INT. A - NIGHT')], 'A');
  assert.equal(m.a.find((i) => /DAY and NIGHT/.test(i.text)).level, 'potential');
  noIssues(C.continuity([sc('a', 1, 'X', 'p1', 's1', 'INT. A'), sc('b', 2, 'X', 'p1', 's1', 'INT. A - LATER')], 'A'));
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

// ---- independent-review regressions: prototype-like user text and direction-aware numeric needs ----
test('user text that looks like a prototype key is ordinary data in groups and scene ids', () => {
  for (const g of ['constructor', '__proto__', 'toString', 'hasOwnProperty', 'valueOf']) {
    const m = C.continuity([sc('toString', 1, g, 'p1', 's1'), sc('hasOwnProperty', 2, g, 'p2', 's2'), sc('c', 3, g, 'p2', 's2')], 'A');
    assert.equal(m.toString.length, 1, g); assert.equal(m.toString[0].level, 'verified');
    assert.equal(m.hasOwnProperty.length >= 1, true);
    assert.equal(Object.getPrototypeOf(m), null);
  }
  // an ungrouped scene named like a prototype key never reads inherited members
  noIssues(C.continuity([sc('constructor', 1, '', 'p1', 's1'), sc('__proto__', 2, '', 'p2', 's2')], 'A'));
});

const need = (text, over) => C.fitCheck({ scene: scene(text), cand: cand(over || {}), built: {} });
const row = (r, label) => r.rows.filter((x) => x.label === label);

test('upper bounds mean upper bounds: "no more than" and "not more than" are never read as minimums', () => {
  assert.equal(row(need('no more than 3 m ceiling', { shot: { ceiling_m: 2.8 } }), 'Ceiling height')[0].kind, 'estimate');   // 2.8 <= 3
  assert.equal(row(need('no more than 3 m ceiling', { shot: { ceiling_m: 3.4 } }), 'Ceiling height')[0].kind, 'conflict');
  assert.equal(row(need('ceilings not more than 3 m', { shot: { ceiling_m: 2.8 } }), 'Ceiling height')[0].kind, 'estimate');
  assert.equal(row(need('not more than 100 sqm', { shot: { room_area_m2: 80 } }), 'Floor area')[0].kind, 'estimate');
  assert.equal(row(need('not more than 100 sqm', { shot: { room_area_m2: 120 } }), 'Floor area')[0].kind, 'conflict');
  assert.equal(row(need('at most 100 m2', { shot: { room_area_m2: 100 } }), 'Floor area')[0].kind, 'estimate');                 // <= includes equality
  assert.equal(row(need('maximum of 50 m²', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'conflict');
  assert.equal(row(need('up to 70 square metres', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'estimate');
  assert.equal(row(need('no less than 40 m2', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'estimate');
  assert.equal(row(need('not less than 90 m2', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'conflict');
});

test('strict inequalities exclude equality; unit conversion applies to upper bounds', () => {
  assert.equal(row(need('more than 60 m2', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'conflict');                 // 60 is not more than 60
  assert.equal(row(need('over 59 m2', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'estimate');
  assert.equal(row(need('less than 60 m2', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'conflict');
  assert.equal(row(need('under 61 m2', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'estimate');
  assert.equal(row(need('no more than 700 sq ft', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'estimate');        // 65.0 m2
  assert.equal(row(need('no more than 600 sq ft', { shot: { room_area_m2: 60 } }), 'Floor area')[0].kind, 'conflict');        // 55.7 m2
});

test('negated or unfamiliar wording is left unread: no guessed minimum or maximum', () => {
  for (const t of ['not at least 100 m2', 'not over 100 m2', 'not under 10 m2', 'not up to 100 sqm']) {
    const r = row(need(t, { shot: { room_area_m2: 60 } }), 'Floor area');
    assert.equal(r.length, 1, t); assert.equal(r[0].kind, 'unknown', t); assert.match(r[0].detail, /does not read as a minimum or maximum/);
  }
  assert.equal(row(need('about 40 m2, roughly 3 m ceiling', {}), 'Floor area').length, 0);                                    // no qualifier: nothing invented
});

test('mixed phrases are each evaluated; estimates and missing values never become a pass', () => {
  const r = need('at least 40 m2 but no more than 50 m2', { shot: { room_area_m2: 60 } });
  const kinds2 = row(r, 'Floor area').map((x) => x.kind).sort();
  assert.deepEqual(kinds2, ['conflict', 'estimate']);                                                                            // 60 >= 40 consistent, 60 <= 50 conflict
  assert.equal(r.summary.matches, 0);                                                                                            // index estimates are never "matches"
  const gone = need('no more than 3 m ceiling', { shot: { ceiling_m: null } });
  assert.equal(row(gone, 'Ceiling height')[0].kind, 'unknown');
  assert.equal(JSON.stringify(need('at least 100 m2', {})).includes('measured'), false);
});

// ---- natural screenplay intake ----
const P = (t, m = 'film') => C.parseScript(t, m);
const heads = (r) => r.scenes.map((s) => s.heading);

test('plain screenplay headings become scenes with their dialogue kept in the description', () => {
  const r = P('FADE IN:\n\nINT. KITCHEN - DAY\n\nMARA stirs a pot.\n\nMARA\nI wrote this for you.\n\nEXT. GARDEN - NIGHT\nRain falls.\n');
  assert.equal(r.error, null); assert.deepEqual(heads(r), ['INT. KITCHEN - DAY', 'EXT. GARDEN - NIGHT']);
  assert.equal(r.scenes[0].description, 'MARA stirs a pot. MARA I wrote this for you.');
  assert.equal(r.scenes[0].dialogue_lines, 1); assert.equal(r.scenes[1].description, 'Rain falls.');
  assert.match(r.notes[0], /1 line before the first heading was not used/);              // title page is reported, not silently dropped
  assert.deepEqual(r.scenes.map((s) => s.id), ['s1', 's2']);
});

test('CRLF, old Mac line endings, blank lines, scene numbers and INT./EXT. forms are handled', () => {
  const crlf = P('INT. A - DAY\r\nOne.\r\n\r\n\r\nINT./EXT. CAR - NIGHT\r\nTwo.\r\n12 EXT. ROAD - DAWN\r\nThree.');
  assert.deepEqual(heads(crlf), ['INT. A - DAY', 'INT./EXT. CAR - NIGHT', '12 EXT. ROAD - DAWN']);
  assert.deepEqual(P('INT. A - DAY\rOne.\rI/E. B - DAY\rTwo.').scenes.map((s) => s.description), ['One.', 'Two.']);
  assert.equal(P('INT. A - DAY').scenes[0].description, 'INT. A - DAY');                  // a heading alone describes itself
});

test('heading-like words inside body text, dialogue or lowercase are not headings', () => {
  const r = P('INT. HALL - DAY\nShe says INT. is a keyword. The sign reads EXT. EXIT.\nint. not a heading\nINTERIOR design matters. EXTERIOR too. INTERESTING.');
  assert.equal(r.scenes.length, 1); assert.match(r.scenes[0].description, /sign reads EXT\. EXIT/); assert.match(r.scenes[0].description, /int\. not a heading/);
});

test('a heading line may carry its own description after a pipe, and all-pipe input keeps the original format', () => {
  assert.deepEqual(P('INT. A - DAY | bright kitchen\nher line').scenes[0].description, 'bright kitchen her line');
  const legacy = P('INT. KITCHEN | first scene\nINT. OFFICE | second scene');
  assert.deepEqual(heads(legacy), ['INT. KITCHEN', 'INT. OFFICE']); assert.equal(legacy.scenes[1].description, 'second scene');
  assert.equal(P('| no heading').error, 'Scene 1 needs a heading before "|".');
  assert.equal(P('').error, 'Add at least one scene line.'); assert.equal(P('  \n\n ').error, 'Add at least one scene line.');
});

test('limits are explicit: nine scenes is an error with the count, long text is cut with a note, nothing disappears silently', () => {
  const nine = Array.from({ length: 9 }, (_, i) => `INT. ROOM ${i + 1} - DAY\nText.`).join('\n\n');
  assert.match(P(nine).error, /Max 8 scenes \(found 9\)\. .*nothing was dropped/);
  assert.equal(P(nine.split('\n\n').slice(0, 8).join('\n\n')).scenes.length, 8);
  const long = P(`INT. HALL - DAY\n${'word '.repeat(400)}`);
  assert.equal(long.scenes[0].description.length, 600); assert.equal(long.scenes[0].truncated, true); assert.match(long.notes.join(' '), /Scene 1 description was cut from \d+ to 600 characters/);
  const head = P(`INT. ${'X'.repeat(300)}\nbody`);                                          // over 200 chars is not treated as a heading line
  assert.match(head.error || head.notes.join(' '), /No scene headings|cut/);
  assert.match(P('x'.repeat(60001)).error, /limit is 60,000/);
  assert.equal(P('INT. ' + 'X'.repeat(150) + '\nbody').scenes[0].heading.length, 120);
});

test('malformed or heading-less prose is an explanation, not guessed scenes', () => {
  const prose = P(Array.from({ length: 12 }, (_, i) => `This is sentence line number ${i} of a plain paragraph.`).join('\n'));
  assert.match(prose.error, /No scene headings found\. Start each scene with INT\. or EXT\./);
  const few = P('A kitchen at night\nA garden in rain');
  assert.equal(few.error, null); assert.equal(few.scenes.length, 2); assert.match(few.notes[0], /No INT\.\/EXT\. headings found, so each line was read as one scene/);
});

test('control characters are removed and a very long script parses quickly and within bounds', () => {
  const r = P('INT. A - DAY\nhe\u0000llo\u0007 world');
  assert.equal(r.scenes[0].description, 'he llo world');
  const big = Array.from({ length: 8 }, (_, i) => `INT. R${i} - DAY\n${'lorem ipsum '.repeat(400)}`).join('\n');
  const t0 = Date.now(); const rb = P(big); assert.ok(Date.now() - t0 < 500); assert.equal(rb.scenes.length, 8);
  assert.ok(rb.scenes.every((s) => s.description.length <= 600));
});

test('community needs are plain paragraphs: INT./EXT. has no meaning, blank lines separate sites', () => {
  const r = P('Distribution hub\nlarge open floor, loading access, INT. is just text\n\nFirst aid point\nquiet room near the entrance', 'community');
  assert.deepEqual(heads(r), ['Distribution hub', 'First aid point']); assert.match(r.scenes[0].description, /INT\. is just text/);
  assert.deepEqual(heads(P('INT. KITCHEN - DAY\nfilm text', 'community')), ['INT. KITCHEN - DAY']);   // a pasted screenplay is one need, never parsed as film
  assert.equal(P('INT. KITCHEN - DAY\nfilm text', 'community').scenes.length, 1);
  assert.equal(P('Hub | open floor\nFirst aid | quiet', 'community').scenes.length, 2);               // pipe lines still work
  assert.equal(P('', 'community').error, 'Add at least one site need.');
  assert.match(P(Array.from({ length: 9 }, (_, i) => `Need ${i}\ntext`).join('\n\n'), 'community').error, /Max 8 needs \(found 9\)/);
});

// ---- Save the scene: outcome, satisfaction and record (pure) ----
const mkCand = (pid, shot, o = {}) => ({ eligible: o.eligible !== false,
  shot: { shot_id: shot, property_id: pid, score: o.score ?? 0.8, room_area_m2: o.area ?? 60, ceiling_m: o.ceil ?? 2.6 },
  property: { availability_status: o.avail ?? null },
  logistics: { parking_status: o.pst ?? null, enough_parking: o.enough ?? null, truck_spaces: o.trucks ?? null }, warnings: [] });
const mkResp = (cands, assign, extra = {}) => ({ mode: 'mock', scenes: [{ id: 's1', candidates: cands }, { id: 's2', candidates: cands }],
  plans: [{ assignments: assign, locations: 1, company_moves: 0, ...extra }] });
const REQ5 = { trucks: 5, cars: 0, require_available: false };
const run = (over) => C.saveSceneOutcome({ sid: 's1', req: REQ5, oldReq: { trucks: 0, cars: 0, require_available: false }, before: { shot_id: 'a1', property_id: 'A' },
  oldCand: mkCand('A', 'a1'), forbidden: [], oldAssign: { s1: { shot_id: 'a1', property_id: 'A' }, s2: { shot_id: 'a2', property_id: 'A' } }, ...over });

test('satisfaction: unknown capacity against a positive truck requirement is never met; estimates are met but labelled', () => {
  const f = (o) => C.candidateFacts(mkCand('A', 'a', o));
  assert.equal(C.satisfaction(f({}), REQ5).parking, 'unknown'); assert.equal(C.satisfaction(f({}), REQ5).satisfied, false);
  assert.equal(C.satisfaction(f({ pst: 'unknown', enough: true }), REQ5).parking, 'unknown');                  // a flag without a status is ignored
  assert.equal(C.satisfaction(f({ pst: 'estimated', enough: false }), REQ5).parking, 'unmet');
  const ok = C.satisfaction(f({ pst: 'estimated', enough: true }), REQ5); assert.equal(ok.parking, 'met'); assert.equal(ok.satisfied, true);
  assert.equal(C.satisfaction(f({}), { trucks: 0, cars: 0, require_available: false }).satisfied, false, 'no requirement means nothing is satisfied');
  assert.equal(C.satisfaction(f({ avail: 'available' }), { trucks: 0, cars: 0, require_available: true }).satisfied, true);
  assert.equal(C.satisfaction(f({ avail: 'available', pst: 'estimated', enough: false }), { trucks: 2, cars: 0, require_available: true }).satisfied, false);
  assert.equal(C.satisfaction(null, REQ5).parking, 'unknown');
});

test('outcome: an estimated alternative is proposed, with the differences stated from real fields and approval left unknown', () => {
  const cands = [mkCand('A', 'a1', { pst: 'estimated', enough: false, score: 0.9 }), mkCand('B', 'b1', { pst: 'estimated', enough: true, score: 0.83, area: 100 }), mkCand('A', 'a2', { score: 0.7 })];
  const r = run({ newResp: mkResp(cands, [{ scene_id: 's1', property_id: 'B', shot_id: 'b1' }, { scene_id: 's2', property_id: 'B', shot_id: 'b2' }]) });
  assert.equal(r.kind, 'alternative'); assert.equal(r.after.shot_id, 'b1'); assert.equal(r.fromPlan, true); assert.equal(r.totalsRecalculated, true);
  const d = r.differences.join('\n');
  assert.match(d, /Requirement: estimated capacity is below 5 trucks and 0 cars → estimated capacity covers 5 trucks and 0 cars \(approval unknown\)/);
  assert.match(d, /Different property: A → B/); assert.match(d, /Floor area \(index estimates, not measurements\): 60 m² → 100 m²/);
  assert.match(d, /Image similarity \(a ranking from the same query, not shootability\): 0\.90 → 0\.83/);
  assert.match(d, /Plan from the revised request: 1 location\(s\), 0 move\(s\)/); assert.equal(/%/.test(d), false);
  assert.equal(r.planChanges.length, 1); assert.equal(r.planChanges[0].scene_id, 's2'); assert.match(d, /also moves 1 other scene/);
  assert.ok(r.unresolved.some((x) => /Parking capacity is an estimate; approval is unknown/.test(x))); assert.ok(r.unresolved.some((x) => /unreviewed drafts; geometric fit is unknown/.test(x)));
});

test('outcome: no alternative, unknown-only data, no requirement, empty plan and ruled-out pools each give an honest non-result', () => {
  const unknownOnly = [mkCand('A', 'a1'), mkCand('B', 'b1')];
  let r = run({ newResp: mkResp(unknownOnly, [{ scene_id: 's1', property_id: 'A', shot_id: 'a1' }]) });
  assert.equal(r.kind, 'none'); assert.match(r.reasons[0], /No candidate has known capacity or availability that satisfies the requirement\. 2 still have unknown data/);
  assert.equal(r.before.sat.parking, 'unknown'); assert.equal(r.after, null);
  const allOut = [mkCand('A', 'a1', { eligible: false, pst: 'estimated', enough: false }), mkCand('B', 'b1', { eligible: false, pst: 'estimated', enough: false })];
  r = run({ newResp: mkResp(allOut, [{ scene_id: 's1', property_id: 'A', shot_id: 'a1' }]) }); assert.equal(r.kind, 'none'); assert.match(r.reasons[0], /Every candidate for this scene is ruled out/); assert.equal(r.before.excluded, true);
  r = run({ req: { trucks: 0, cars: 0, require_available: false }, newResp: mkResp(unknownOnly, []) }); assert.equal(r.kind, 'none'); assert.match(r.reasons[0], /No requirement was entered/);
  r = run({ newResp: { scenes: [], plans: [] } }); assert.equal(r.kind, 'none'); assert.match(r.reasons[0], /returned no plan/);
  r = run({ newResp: null }); assert.equal(r.kind, 'none');
  const candsOk = [mkCand('A', 'a1', { pst: 'estimated', enough: true })];                                   // the current frame already satisfies it
  r = run({ newResp: mkResp(candsOk, [{ scene_id: 's1', property_id: 'A', shot_id: 'a1' }]) }); assert.equal(r.kind, 'already'); assert.equal(r.after, null);
});

test('outcome: rejected properties and stale-looking pool members are never proposed; only the revised response counts', () => {
  const cands = [mkCand('A', 'a1', { pst: 'estimated', enough: false }), mkCand('B', 'b1', { pst: 'estimated', enough: true }), mkCand('C', 'c1', { pst: 'measured', enough: true, score: 0.5 })];
  let r = run({ forbidden: ['B'], newResp: mkResp(cands, [{ scene_id: 's1', property_id: 'C', shot_id: 'c1' }]) });
  assert.equal(r.kind, 'alternative'); assert.equal(r.after.property_id, 'C');
  r = run({ forbidden: ['B', 'C'], newResp: mkResp(cands, [{ scene_id: 's1', property_id: 'A', shot_id: 'a1' }]) }); assert.equal(r.kind, 'none');
  // an ineligible candidate that looks satisfied is not proposed
  r = run({ newResp: mkResp([mkCand('A', 'a1'), mkCand('B', 'b1', { eligible: false, pst: 'estimated', enough: true })], [{ scene_id: 's1', property_id: 'A', shot_id: 'a1' }]) }); assert.equal(r.kind, 'none');
  // when the solver's own choice is not satisfied, the best satisfied candidate is a hand choice and totals are stated as not recalculated
  r = run({ newResp: mkResp([mkCand('A', 'a1'), mkCand('B', 'b1', { pst: 'estimated', enough: true, score: 0.6 }), mkCand('C', 'c1', { pst: 'estimated', enough: true, score: 0.9 })], [{ scene_id: 's1', property_id: 'A', shot_id: 'a1' }]) });
  assert.equal(r.after.shot_id, 'c1'); assert.equal(r.fromPlan, false); assert.equal(r.totalsRecalculated, false); assert.match(r.differences.join('\n'), /not recalculated for this hand choice/);
  // identical results are deterministic
  assert.deepEqual(run({ newResp: mkResp([mkCand('B', 'z', { pst: 'estimated', enough: true }), mkCand('C', 'y', { pst: 'estimated', enough: true })], []) }).after?.shot_id, 'y');
});

test('decision record is compact, bounded, whitelisted and free of provider rows', () => {
  const cands = [mkCand('A', 'a1', { pst: 'estimated', enough: false }), mkCand('B', 'b1', { pst: 'estimated', enough: true })];
  const o = run({ newResp: mkResp(cands, [{ scene_id: 's1', property_id: 'B', shot_id: 'b1' }]) });
  const rec = C.decisionRecord(o, { trucks: 0, cars: 0, require_available: false }, { trucks: 99, cars: 999, require_available: true }, '2026-11-14T10:00:00.000Z');
  assert.deepEqual(Object.keys(rec).sort(), ['after', 'before', 'decided_at', 'differences', 'moved_scenes', 'original', 'revised', 'scope', 'totals_recalculated', 'unresolved', 'v']);
  assert.deepEqual(rec.revised, { trucks: 20, cars: 200, require_available: true });
  assert.deepEqual(Object.keys(rec.after).sort(), ['area_m2', 'availability', 'ceiling_m', 'enough_parking', 'parking_status', 'property_id', 'shot_id', 'similarity']);
  const text = JSON.stringify(rec); for (const leak of ['image_path', 'address', 'contact', 'api_key', 'warnings', 'logistics']) assert.equal(text.includes(leak), false, leak);
  assert.equal(rec.scope, 'whole_plan'); assert.ok(rec.differences.length <= 8 && rec.unresolved.length <= 8);
});
