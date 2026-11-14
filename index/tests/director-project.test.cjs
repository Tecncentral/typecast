'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { normalizeProject, restoreEdits, MAX_BYTES } = require('../director-project.js');
const clone = (value) => JSON.parse(JSON.stringify(value));
const shot = () => ({ duration_sec: 7, dialogue: 'Enter quietly.', actors: [
  { id: 'a1', name: 'Mara', pose: 'walk', x0: .2, y0: .8, x1: .7, y1: .8, scale: 1 },
] });
const project = () => ({ app: 'Typecast Director', variant: 'B', exported_at: '2026-11-14T20:00:00Z',
  source_mode: 'live', scenes: [{ id: 's1', heading: 'INT. OFFICE', description: 'An arrival',
    evidence: { frame: { shot_id: 'saved-view', property_id: 'property-1', model_id: 'model-1' },
      property: { address: 'should never be retained' } }, staging: shot(), variants: { A: shot(), B: shot() } }] });
const response = () => ({ plans: [{ assignments: [{ scene_id: 's1', property_id: 'property-1', shot_id: 'new-best-view' }] }],
  scenes: [{ id: 's1', candidates: [{ eligible: true, shot: { property_id: 'property-1', shot_id: 'saved-view' } }] }] });

test('actual export shape preserves both variants, strips evidence and arbitrary fields', () => {
  const input = project();
  input.provider_key = 'discard-me'; input.scenes[0].image_url = 'https://untrusted.invalid/image';
  const normalized = normalizeProject(JSON.stringify(input));
  assert.deepEqual(normalized.scenes[0].variants.B, shot());
  assert.deepEqual(normalized.scenes[0].evidence, { frame: { shot_id: 'saved-view', property_id: 'property-1' } });
  assert.equal(JSON.stringify(normalized).includes('discard-me'), false);
  assert.equal(JSON.stringify(normalized).includes('untrusted'), false);
  assert.equal(JSON.stringify(normalized).includes('address'), false);
  assert.deepEqual(normalizeProject(normalized), normalized);
});

test('restores saved view only as a manual frame within the same assigned property', () => {
  const input = project(), current = response(), before = clone(input);
  const restored = restoreEdits(input, current);
  assert.equal(restored.restored, 1);
  assert.deepEqual(restored.edits['s1::saved-view'].A, shot());
  assert.equal(restored.frameOverrides['0::s1'], 'saved-view');
  assert.deepEqual(restored.reviewNeeded, []);
  assert.deepEqual(input, before);
  restored.edits['s1::saved-view'].A.dialogue = 'changed';
  assert.equal(input.scenes[0].variants.A.dialogue, 'Enter quietly.');
});

for (const reason of ['property changed', 'frame missing', 'ineligible', 'candidate property changed', 'uncovered']) {
  test(`retains staging for review when ${reason}; never registers it on a replacement frame`, () => {
    const current = response();
    if (reason === 'property changed') current.plans[0].assignments[0].property_id = 'property-2';
    if (reason === 'frame missing') current.scenes[0].candidates[0].shot.shot_id = 'other-view';
    if (reason === 'ineligible') current.scenes[0].candidates[0].eligible = false;
    if (reason === 'candidate property changed') current.scenes[0].candidates[0].shot.property_id = 'property-2';
    if (reason === 'uncovered') current.plans[0].assignments = [];
    const restored = restoreEdits(project(), current);
    assert.equal(restored.restored, 0);
    assert.deepEqual(Object.keys(restored.edits), []);
    assert.deepEqual(Object.keys(restored.frameOverrides), []);
    assert.equal(restored.reviewNeeded[0].frame.shot_id, 'saved-view');
    assert.deepEqual(restored.reviewNeeded[0].variants.B, shot());
    assert.match(restored.reviewNeeded[0].reason, /Review/);
    const savedAgain = normalizeProject({ ...project(), scenes: project().scenes.map((scene) => ({ ...scene, variants: null, staging: null })),
      review_needed: restored.reviewNeeded });
    assert.equal(restoreEdits(savedAgain, response()).restored, 1);
  });
}

test('legacy staging-only export restores selected variant and leaves the other blank', () => {
  const input = project(); delete input.scenes[0].variants;
  const normalized = normalizeProject(input);
  assert.deepEqual(normalized.scenes[0].variants.B, shot());
  assert.deepEqual(normalized.scenes[0].variants.A, { duration_sec: 5, dialogue: '', actors: [] });
});

test('uncovered scenes remain uncovered without fabricated frame identity', () => {
  const input = project(); Object.assign(input.scenes[0], { evidence: null, staging: null, variants: null });
  assert.equal(normalizeProject(input).scenes[0].evidence, null);
  assert.equal(restoreEdits(input, response()).restored, 0);
  input.scenes[0].staging = shot();
  assert.throws(() => normalizeProject(input), /requires a saved frame/);
});

const invalid = [
  ['app', (p) => { p.app = 'other'; }], ['variant', (p) => { p.variant = 'C'; }],
  ['empty scenes', (p) => { p.scenes = []; }], ['too many scenes', (p) => { p.scenes = Array.from({ length: 9 }, () => clone(p.scenes[0])); }],
  ['duplicate scenes', (p) => { p.scenes.push(clone(p.scenes[0])); }],
  ['heading bound', (p) => { p.scenes[0].heading = 'h'.repeat(121); }],
  ['description bound', (p) => { p.scenes[0].description = 'd'.repeat(1001); }],
  ['frame URL', (p) => { p.scenes[0].evidence.frame.shot_id = 'https://example.com/image'; }],
  ['actor count', (p) => { p.scenes[0].variants.A.actors = Array.from({ length: 4 }, () => shot().actors[0]); }],
  ['duplicate actors', (p) => { p.scenes[0].variants.A.actors.push(clone(p.scenes[0].variants.A.actors[0])); }],
  ['pose', (p) => { p.scenes[0].variants.A.actors[0].pose = 'fly'; }],
  ['coordinates', (p) => { p.scenes[0].variants.A.actors[0].x1 = 1.1; }],
  ['nonfinite', (p) => { p.scenes[0].variants.A.actors[0].y0 = NaN; }],
  ['boolean coordinate', (p) => { p.scenes[0].variants.A.actors[0].y1 = true; }],
  ['duration low', (p) => { p.scenes[0].variants.A.duration_sec = 0; }],
  ['duration high', (p) => { p.scenes[0].variants.B.duration_sec = 31; }],
  ['scale', (p) => { p.scenes[0].variants.B.actors[0].scale = 3; }],
  ['dialogue', (p) => { p.scenes[0].variants.B.dialogue = 'd'.repeat(801); }],
];
for (const [name, mutate] of invalid) test(`rejects invalid ${name}`, () => {
  const input = project(); mutate(input); assert.throws(() => normalizeProject(input), /Invalid project/);
});

test('rejects prototype keys even inside stripped evidence; does not pollute prototypes', () => {
  for (const key of ['__proto__', 'constructor', 'prototype']) {
    const input = JSON.stringify(project()).replace('"source_mode":"live"', `"source_mode":"live","ignored":{"${key}":{"polluted":true}}`);
    assert.throws(() => normalizeProject(input), /unsafe object key/);
  }
  assert.equal({}.polluted, undefined);
  const input = project(); Object.defineProperty(input, 'untrusted', { get() { throw new Error('getter ran'); }, enumerable: true });
  assert.throws(() => normalizeProject(input), /unsafe object key/);
});

test('rejects non-JSON, oversized and excessively nested input without partial edits', () => {
  assert.throws(() => normalizeProject('{'), /not JSON/);
  assert.throws(() => normalizeProject(' '.repeat(MAX_BYTES + 1)), /exceeds/);
  const input = project(); input.extra = {}; let node = input.extra;
  for (let i = 0; i < 20; i++) node = node.next = {};
  assert.throws(() => normalizeProject(input), /complex/);
  assert.throws(() => restoreEdits(project(), { plans: [], scenes: [] }), /current production plan/);
});
