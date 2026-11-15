// Per-conversation delivery for the Photon runner and the simulator (one code path for both).
// - Messages that arrive within MERGE_MS of the first one in a conversation are merged into one input.
// - Replies are sent one at a time, in order; a conversation never interleaves with itself.
// - At most BUDGET outbound messages per search (questions, confirmation, results, link), counted per conversation.
// - A non-text message gets one short notice (until the next text message).
// - A failed results bubble is replaced by a short fallback line. Nothing here prints message text or ids.
export const MERGE_MS = 2000;
export const BUDGET = 8;
export const NON_TEXT_NOTICE = "I can only read text for now: describe the scene in words.";
export const RESULTS_FAILED = "Pick list couldn't be sent, open the link instead.";

export function createConversations({
  handle, send, split = (t) => [t], wait, log = () => {}, onError = () => {}, onAnswered = () => {},
  fetchImpl, env, mergeMs = MERGE_MS, budget = BUDGET, onResultsSent,
}) {
  const states = new Map();
  let nextIndex = 1;

  const stateFor = (spaceId) => {
    if (!states.has(spaceId)) states.set(spaceId, { index: nextIndex++, pending: [], scheduled: false, queue: Promise.resolve(), count: 0, flowDone: false, noticed: false, sent: 0, dropped: 0 });
    return states.get(spaceId);
  };

  async function processBatch(state, batch) {
    const first = batch[0];
    const texts = batch.filter((m) => !m.nonText).map((m) => m.text);
    let n = 0;
    if (state.flowDone) state.count = 0;

    const out = async (text, meta = {}) => {
      if (meta.flow === "start") { state.count = 0; state.flowDone = false; }
      let failedResults = false;
      for (const piece of split(text)) {
        if (state.count >= budget) { state.dropped += 1; continue; }
        state.count += 1; state.sent += 1;
        if (!(await send(first, n++, piece)) && meta.role === "results") failedResults = true;
      }
      if (failedResults && state.count < budget) { state.count += 1; state.sent += 1; await send(first, n++, RESULTS_FAILED); }
      if (meta.flow === "end") state.flowDone = true;
    };

    try {
      if (batch.some((m) => m.nonText) && !state.noticed) { state.noticed = true; await out(NON_TEXT_NOTICE); }
      if (texts.length) {
        state.noticed = false;
        const parts = await handle(first.spaceId, texts.join(" "), { say: out, fetchImpl, env, sender: first.senderHash });
        for (const part of parts) if (part.text) await out(part.text, part);
        onAnswered();
        // After the results and link were sent: the hook may save the search. A failure there never blocks replies.
        if (onResultsSent && parts.some((p) => p.flow === "end")) {
          try { onResultsSent({ spaceId: first.spaceId, senderHash: first.senderHash, count: state.count }); } catch (e) { onError(e); }
        }
      }
    } catch (e) { onError(e); }
    log(`conversation ${state.index}: ${state.count} of ${budget} outbound in this search${state.dropped ? `, ${state.dropped} over the limit were not sent` : ""}`);
  }

  /** Queue one accepted message ({ id, spaceId, senderId, text, nonText }). */
  function submit(m) {
    const state = stateFor(m.spaceId);
    state.pending.push(m);
    if (state.scheduled) return;
    state.scheduled = true;
    state.queue = state.queue.then(async () => {
      await wait(mergeMs);
      state.scheduled = false;
      await processBatch(state, state.pending.splice(0));
    });
  }

  return { submit, idle: () => Promise.all([...states.values()].map((s) => s.queue)), stats: () => [...states.values()].map((s) => ({ conversation: s.index, sent: s.sent, dropped: s.dropped })) };
}
