/* Pure project import helpers. Imported facts never replace current source evidence. */
(function (root) {
  'use strict';
  const MAX_BYTES = 1024 * 1024;
  const badKeys = new Set(['__proto__', 'prototype', 'constructor']);
  const fail = (message) => { throw new Error(`Invalid project: ${message}`); };
  function inspect(value, depth = 0, budget = { nodes: 0, seen: new Set() }) {
    if (++budget.nodes > 10000 || depth > 16) fail('file is too complex');
    if (typeof value === 'number' && !Number.isFinite(value)) fail('nonfinite number');
    if (value == null || typeof value !== 'object') {
      if (!['string', 'number', 'boolean', 'undefined'].includes(typeof value) && value !== null) fail('unsupported value');
      return;
    }
    if (budget.seen.has(value)) fail('repeated or cyclic object');
    budget.seen.add(value);
    if (!Array.isArray(value) && ![Object.prototype, null].includes(Object.getPrototypeOf(value))) fail('expected plain JSON');
    for (const [key, descriptor] of Object.entries(Object.getOwnPropertyDescriptors(value))) {
      if (badKeys.has(key) || descriptor.get || descriptor.set) fail('unsafe object key');
      inspect(descriptor.value, depth + 1, budget);
    }
  }
  function record(value, name) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${name} must be an object`);
    return value;
  }
  function text(value, name, limit, empty = false) {
    if (typeof value !== 'string' || value.length > limit || (!empty && !value.trim())) fail(`${name} must be ${empty ? '0' : '1'}..${limit} characters`);
    return value;
  }
  function id(value, name, limit = 120) {
    text(value, name, limit);
    if (!/^[\w.:-]+$/.test(value) || badKeys.has(value)) fail(`${name} has invalid characters`);
    return value;
  }
  function number(value, name, low, high) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value < low || value > high) fail(`${name} must be within ${low}..${high}`);
    return value;
  }
  const blank = () => ({ duration_sec: 5, dialogue: '', actors: [] });
  function shot(value) {
    record(value, 'staging');
    if (!Array.isArray(value.actors) || value.actors.length > 3) fail('at most three actors are allowed');
    const actors = value.actors.map((actor) => {
      record(actor, 'actor');
      if (!['stand', 'sit', 'walk'].includes(actor.pose)) fail('actor pose');
      return { id: id(actor.id, 'actor id', 32), name: text(actor.name, 'actor name', 24), pose: actor.pose,
        x0: number(actor.x0, 'x0', 0, 1), y0: number(actor.y0, 'y0', 0, 1),
        x1: number(actor.x1, 'x1', 0, 1), y1: number(actor.y1, 'y1', 0, 1), scale: number(actor.scale, 'scale', .3, 2) };
    });
    if (new Set(actors.map((actor) => actor.id)).size !== actors.length) fail('duplicate actor ids');
    // Provenance whitelist: exactly one known value, otherwise the file is refused (no free-text origin labels).
    if (value.origin != null && value.origin !== 'authored-sample') fail('unsupported take origin');
    const out = { duration_sec: number(value.duration_sec, 'duration', 1, 30),
      dialogue: text(value.dialogue, 'dialogue', 800, true), actors };
    if (value.origin === 'authored-sample') out.origin = 'authored-sample';
    return out;
  }
  function variants(value) {
    record(value, 'variants');
    return { A: shot(value.A), B: shot(value.B) };
  }
  // Optional production state added by the Director. Strict whitelists: identifiers, one boolean, bounded text.
  function notesOf(value) {
    record(value, 'notes');
    const dressing = value.dressing == null ? '' : text(value.dressing, 'dressing notes', 600, true);
    const group = value.group == null ? '' : text(value.group, 'continuity link', 12, true);
    if (group && !/^[A-Za-z0-9_-]+$/.test(group)) fail('continuity link has invalid characters');
    return { dressing: dressing.replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, ''), group };
  }
  function choiceOf(value) {
    record(value, 'location choice');
    if (typeof value.staging_reviewed !== 'boolean') fail('location choice needs staging_reviewed');
    return { shot_id: id(value.shot_id, 'swapped shot id'), property_id: id(value.property_id, 'swapped property id'),
      from_shot_id: id(value.from_shot_id, 'original shot id'), from_property_id: id(value.from_property_id, 'original property id'),
      staging_reviewed: value.staging_reviewed };
  }
  function frame(value) {
    record(value, 'frame identity');
    return { shot_id: id(value.shot_id, 'shot id'), property_id: id(value.property_id, 'property id') };
  }
  function normalizeProject(payload) {
    if (typeof payload === 'string') {
      if (payload.length > MAX_BYTES) fail('file exceeds 1 MB');
      try { payload = JSON.parse(payload); } catch { fail('file is not JSON'); }
    }
    inspect(payload); record(payload, 'project');
    if (payload.app !== 'Typecast Director') fail('unsupported app');
    if (!['A', 'B'].includes(payload.variant)) fail('variant must be A or B');
    if (!Array.isArray(payload.scenes) || payload.scenes.length < 1 || payload.scenes.length > 8) fail('one to eight scenes are required');
    const scenes = payload.scenes.map((scene) => {
      record(scene, 'scene');
      const savedFrame = scene.evidence?.frame == null ? null : frame(scene.evidence.frame);
      let savedVariants = scene.variants == null ? null : variants(scene.variants);
      const staging = scene.staging == null ? null : shot(scene.staging);
      if (!savedVariants && staging) { savedVariants = { A: blank(), B: blank() }; savedVariants[payload.variant] = staging; }
      if (savedVariants && !savedFrame) fail('staging requires a saved frame identity');
      const out = { id: id(scene.id, 'scene id', 60), heading: text(scene.heading, 'heading', 120),
        description: text(scene.description, 'description', 1000),
        evidence: savedFrame ? { frame: savedFrame } : null, variants: savedVariants };
      if (scene.notes != null) out.notes = notesOf(scene.notes);
      if (scene.location_choice != null) {
        if (!savedFrame) fail('a location choice needs a saved frame identity');
        out.location_choice = choiceOf(scene.location_choice);
      }
      return out;
    });
    if (new Set(scenes.map((scene) => scene.id)).size !== scenes.length) fail('duplicate scene ids');
    const pending = payload.review_needed ?? [];
    if (!Array.isArray(pending) || pending.length > 8) fail('at most eight review drafts are allowed');
    const reviewNeeded = pending.map((entry) => {
      record(entry, 'review draft');
      const sceneId = id(entry.scene_id, 'review scene id', 60);
      if (!scenes.some((scene) => scene.id === sceneId)) fail('review draft references a missing scene');
      return { scene_id: sceneId, frame: frame(entry.frame), variants: variants(entry.variants) };
    });
    // Every field is explicitly copied. Source metrics, URLs, unknown keys and
    // provider records in an exported file are deliberately not trusted or retained.
    return { app: 'Typecast Director', variant: payload.variant, scenes, review_needed: reviewNeeded };
  }
  function restoreEdits(payload, response, planIndex = 0) {
    const project = normalizeProject(payload);
    if (!Number.isInteger(planIndex) || planIndex < 0 || !Array.isArray(response?.plans) || !response.plans[planIndex]
        || !Array.isArray(response.scenes)) fail('a current production plan is required');
    const assignments = response.plans[planIndex].assignments;
    if (!Array.isArray(assignments)) fail('current plan has no assignments');
    const edits = Object.create(null), frameOverrides = Object.create(null), reviewNeeded = [], swaps = Object.create(null), transfers = Object.create(null), notes = Object.create(null);
    for (const scene of project.scenes) if (scene.notes && (scene.notes.dressing || scene.notes.group)) notes[scene.id] = scene.notes;
    const saved = project.scenes.filter((scene) => scene.variants).map((scene) => ({
      scene_id: scene.id, frame: scene.evidence.frame, variants: scene.variants, choice: scene.location_choice || null,
    })).concat(project.review_needed);
    let restored = 0;
    const processed = new Set();
    for (const entry of saved) {
      const marker = `${entry.scene_id}::${entry.frame.property_id}::${entry.frame.shot_id}`;
      if (processed.has(marker)) continue;
      processed.add(marker);
      const assignment = assignments.find((item) => item.scene_id === entry.scene_id);
      const scene = response.scenes.find((item) => item.id === entry.scene_id);
      const eligible = scene?.candidates?.some((candidate) =>
        candidate.eligible === true && candidate.shot?.shot_id === entry.frame.shot_id && candidate.shot?.property_id === entry.frame.property_id);
      const match = assignment?.property_id === entry.frame.property_id && eligible;
      // A hand-chosen location is restored only if the same exact frame is still an eligible candidate in the fresh pool.
      const swap = !match && eligible && assignment && entry.choice && entry.choice.shot_id === entry.frame.shot_id
        && entry.choice.property_id === entry.frame.property_id;
      const slot = `${planIndex}::${entry.scene_id}`;
      if ((match || swap) && !Object.hasOwn(frameOverrides, slot) && !Object.hasOwn(swaps, slot)) {
        edits[`${entry.scene_id}::${entry.frame.shot_id}`] = entry.variants;
        if (swap) {
          swaps[slot] = { shot_id: entry.choice.shot_id, property_id: entry.choice.property_id, from_shot_id: entry.choice.from_shot_id, from_property_id: entry.choice.from_property_id };
          if (!entry.choice.staging_reviewed) transfers[`${entry.scene_id}::${entry.frame.shot_id}`] = { from_shot_id: entry.choice.from_shot_id, from_property_id: entry.choice.from_property_id, reviewed: false };
        } else frameOverrides[slot] = entry.frame.shot_id;
        restored++;
      } else reviewNeeded.push({ ...entry, reason: 'Saved frame is unavailable, ineligible, assigned to another property, or another draft is already restored. Review staging before reuse.' });
    }
    if (reviewNeeded.length > 8) fail('too many unresolved drafts; retain the original file');
    return { edits, frameOverrides, reviewNeeded, restored, swaps, transfers, notes };
  }
  const api = { normalizeProject, restoreEdits, MAX_BYTES };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.TypecastProject = Object.freeze(api);
})(typeof globalThis === 'object' ? globalThis : this);
