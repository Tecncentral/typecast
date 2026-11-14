/**
 * Viewfinder dressed-set regressions ported from the PR35 audit (origin/cursor/pr30-regression-audit-c56a
 * 02f5d64, baseline dbceec2), where they were `todo`. They now pass against the fixed viewfinder.
 * Double: vm-evaluated source with fake fetch/Image; no real decode, GPU or pixels.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const source = fs.readFileSync(
  path.join(path.dirname(fileURLToPath(import.meta.url)), '../../web/viewfinder.js'),
  'utf8',
).replace('export { Viewfinder, shotIdFromSrc };', 'globalThis.TestViewfinder = Viewfinder;');

async function loadDressed(label, decodeOk) {
  const context = {
    document: { body: {}, querySelectorAll: () => [] },
    MutationObserver: class { observe() {} },
    fetch: async () => ({
      ok: true,
      json: async () => ({
        label,
        scene: 'INT. KITCHEN - DAY.',
        faces: [{ yaw_deg: 0, pitch_deg: 0, tan_h: 1, tan_v: 0.5, dressed_url: '/cache/worlds/m/s/dressed/dressed_0.jpg' }],
      }),
    }),
    Image: class {
      decode() {
        return decodeOk ? Promise.resolve() : Promise.reject(new Error('missing'));
      }
    },
    matchMedia: () => ({ matches: true }),
    cancelAnimationFrame() {},
    requestAnimationFrame() { return 1; },
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  const nodes = new Map();
  const vf = Object.create(context.TestViewfinder.prototype);
  Object.assign(vf, {
    dialog: { open: true, classList: { contains: () => false } },
    generation: 1,
    renderer: { setDressedFace() {} },
    $(sel) {
      if (!nodes.has(sel)) nodes.set(sel, { textContent: '', hidden: true });
      return nodes.get(sel);
    },
  });
  await vf.loadDressed('shot', 1, vf.renderer);
  return { badge: nodes.get('.vf-ai-badge')?.textContent ?? '', dress: nodes.get('.vf-dress') ?? { hidden: true }, status: nodes.get('.vf-status')?.textContent ?? '' };
}

const CANON = 'AI-imagined set dressing, not the real room';

test('dressed badge keeps the canonical imagined label', async () => {
  const { badge } = await loadDressed('Real captured Matterport property photograph', true);
  assert.equal(badge.startsWith(CANON), true, badge);
  assert.equal(badge.includes('Real captured'), false, badge);
});

test('a missing dressed image is not announced as ready', async () => {
  const { dress, status, badge } = await loadDressed(CANON, false);
  assert.equal(dress.hidden, true);
  assert.equal(badge, '', 'no dressed badge text for an undecoded set');
  assert.equal(/ready/i.test(status), false, status);
});
