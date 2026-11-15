import test from "node:test";
import assert from "node:assert/strict";

let n = 0;
async function load(search, { hasForm = true } = {}) {
  const box = { value: "" };
  const log = { submitted: 0, replaced: null };
  const form = { requestSubmit() { log.submitted += 1; } };
  globalThis.location = { search, pathname: "/app/", hash: "" };
  globalThis.document = { getElementById: (id) => (!hasForm ? null : id === "scene" ? box : id === "scene-form" ? form : null) };
  globalThis.history = { replaceState: (_s, _t, url) => { log.replaced = url; } };
  await import(`../deeplink.js?run=${n++}`);
  return { box, log };
}

test("scene and autorun=1 fill the box, submit once, and drop autorun from the address", async () => {
  const { box, log } = await load("?scene=INT.%20OFFICE%2C%20DAY&autorun=1");
  assert.equal(box.value, "INT. OFFICE, DAY");
  assert.equal(log.submitted, 1);
  assert.equal(log.replaced, "/app/?scene=INT.+OFFICE%2C+DAY");
});

test("without autorun=1, or without a scene, nothing happens", async () => {
  for (const search of ["?scene=INT.%20OFFICE", "?autorun=1", "", "?scene=%20%20&autorun=1", "?scene=x&autorun=0"]) {
    const { box, log } = await load(search);
    assert.equal(box.value, ""); assert.equal(log.submitted, 0); assert.equal(log.replaced, null);
  }
});

test("a very long scene is cut to 2000 characters", async () => {
  const { box } = await load(`?scene=${"a".repeat(5000)}&autorun=1`);
  assert.equal(box.value.length, 2000);
});

test("a page without the scene form is left alone", async () => {
  const { log } = await load("?scene=x&autorun=1", { hasForm: false });
  assert.equal(log.submitted, 0); assert.equal(log.replaced, null);
});

test("markup in the scene is kept as plain text in the box value", async () => {
  const { box } = await load("?scene=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E&autorun=1");
  assert.equal(box.value, "<img src=x onerror=alert(1)>");
});
