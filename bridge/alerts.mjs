// SIMULATED reminders and price alerts. Every price here comes from a simulated source, never a real one.
// - "ALERTS ON" / "ALERTS OFF" (keyword match, no LLM) sets alerts_on for the sender's latest search.
// - After results are sent, the brief, search and picks are saved (mock only). No message text is stored.
// - One reminder per search when alerts are on, no reach-out was drafted, and REMINDER_AFTER_MIN has passed.
// - Price alerts follow the 2-checks rule. Alerts go only to the allowlisted sender, count against the
//   8-outbound cap per search, and are dry-run (counts only) unless PHOTON_ALERTS_REAL=1 and the mock-only guard passes.
import { sessions } from "./core.mjs";
import { buildScene } from "./intake.mjs";
import { buildExterior } from "./scout-v2.mjs";
import { BUDGET } from "./conversations.mjs";
import { hashSender, sqlTime } from "./store.mjs";

export const DEFAULT_REMINDER_AFTER_MIN = 1440;
export const DEFAULT_PRICE_CHECK_MIN = 60;
export const PRICE_LABEL = "SIMULATED price update (demo):";
const KEYWORD = /^\s*alerts\s+(on|off)\s*[.!]?\s*$/i;
const YES = /^\s*(yes|y|send it|approve)\s*[.!]?\s*$/i;
const MULTIFAMILY = /multi-?\s*family/i;

/** "on", "off" or null. Whole-message keyword match. */
export function alertsKeyword(text) {
  const m = KEYWORD.exec(String(text ?? ""));
  return m ? m[1].toLowerCase() : null;
}

/** Default simulated rent: the saved reference rent moved on a fixed cycle, so a demo can cross the budget line. */
export function simulatedRentSource(factors = [1, 1.25, 1.25, 0.8, 0.8]) {
  return (pick, { checkNo }) => (pick.rent_ref == null ? null : Math.round(pick.rent_ref * factors[checkNo % factors.length] * 100) / 100);
}

const number = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);
const verdictFor = (rent, maxRent) => (rent <= maxRent ? "within" : "above");

export function priceAlertText(pick, { rent, maxRent, rentUnits, verdict }) {
  const unit = rentUnits ? ` ${rentUnits}` : "";
  const where = verdict === "above" ? "above" : "back within";
  const retail = MULTIFAMILY.test(pick.property_type ?? "") ? " Multifamily rents here are ground-floor retail rents." : "";
  return `${PRICE_LABEL} ${pick.address} is now ${where} your max rent (${rent}${unit} against ${maxRent}${unit}).${retail} Reply ALERTS OFF to stop.`;
}

export const reminderText = () =>
  'Reminder (demo): you have not drafted a note to any owner for your latest search yet. Reply "draft 1" to start one, or ALERTS OFF to stop reminders.';

export function createAlerts({
  store, allowed = new Set(), env = process.env, now = Date.now, log = console.log,
  rentSource = simulatedRentSource(), guard = async () => {}, dryRun = false,
}) {
  const allowedHashes = new Set([...allowed].map((handle) => hashSender(handle)));
  const shadow = new Map();          // dry run: price state is kept here, never written
  const checkCounts = new Map();     // searchId|propertyId -> checks so far
  let lastPriceCheck = -Infinity;
  const real = () => env.PHOTON_ALERTS_REAL === "1" && !dryRun;
  const minutes = (name, fallback) => (Number(env[name]) > 0 ? Number(env[name]) : fallback);

  /** Reply to ALERTS ON / OFF. */
  function optIn(senderHash, on) {
    const id = store.setAlertsOn(senderHash, on);
    if (id == null) return on ? "Run a search first, then text ALERTS ON." : "There is no search to change alerts for yet.";
    store.addOutbound(id, 1);
    return on
      ? "Alerts are ON for your latest search. This is a simulated demo: any price updates are not real."
      : "Alerts are OFF for your latest search.";
  }

  /** After the results were sent: save the brief, search and picks (mock only, no message text). Returns the search id or null. */
  function saveResults({ spaceId, senderHash, count }) {
    const s = sessions.get(spaceId);
    if (!senderHash || !s?.threadId || !s.v2?.st) return null;
    const slots = s.v2.st.slots;
    const userId = store.upsertUser(senderHash);
    const conversationId = store.upsertConversation(spaceId, userId);
    const briefId = store.saveBrief({
      userId, channel: "imessage",
      interiorScene: slots.setting ? buildScene({ ...slots, ie: "INT" }) : null,
      exteriorQuery: slots.exterior ? buildExterior(slots) : null,
      city: slots.city, trucks: slots.trucks, crewCars: slots.cars,
    });
    let searchId = store.searchByThread(s.threadId);
    if (searchId == null) {
      searchId = store.saveSearch({ briefId, userId, threadId: s.threadId, sourceMode: "mock", createdAt: sqlTime(now()) });
      store.savePicks(searchId, (s.picks ?? []).map((p) => ({
        rank: p.rank, propertyId: p.property.property_id, address: p.property.address, propertyType: p.property.type ?? null,
        rentRef: number(p.rent_ref), rentTier: p.rent_tier ?? null, driveMin: number(p.drive_min),
      })));
    }
    store.setOutboundCount(searchId, count);
    store.setCurrentSearch(conversationId, searchId);
    return searchId;
  }

  /** Wrap the conversation handler: intercept the keywords, and note a saved draft as a reach-out. */
  const wrapHandle = (inner) => async (key, text, ctx) => {
    const keyword = alertsKeyword(text);
    if (keyword && ctx.sender) return [{ text: optIn(ctx.sender, keyword === "on") }];
    // core.mjs clears awaitingApproval on this same object, so read it before the call.
    const { awaitingApproval: rank, threadId } = sessions.get(key) ?? {};
    const parts = await inner(key, text, ctx);
    if (ctx.sender && rank && YES.test(text) && parts.some((p) => /^Saved as a local draft/.test(p.text ?? ""))) {
      const searchId = store.searchByThread(threadId);
      if (searchId != null) store.recordReachOut(searchId, rank, new Date(now()).toISOString());
    }
    return parts;
  };

  const getState = (sid, pid) => (dryRun || !real() ? shadow.get(`${sid}|${pid}`) : null) ?? store.getPriceState(sid, pid);
  const putState = (sid, pid, row) => { if (real()) store.savePriceState(sid, pid, row); else shadow.set(`${sid}|${pid}`, row); };

  /**
   * One pass. `send(spaceId, idempotencyKey, text)` resolves to "sent", "failed" or "no_route".
   * Returns counts only; never logs message text.
   */
  async function tick({ send }) {
    const counts = { reminders: 0, priceAlerts: 0, capped: 0, noRoute: 0, blocked: 0, failed: 0 };
    if (real()) {
      try { await guard(); } catch { log("alerts paused: the API is not in mock mode"); return counts; }
    }
    const t = now();
    const afterMs = minutes("REMINDER_AFTER_MIN", DEFAULT_REMINDER_AFTER_MIN) * 60_000;
    const priceDue = t - lastPriceCheck >= minutes("PRICE_CHECK_MIN", DEFAULT_PRICE_CHECK_MIN) * 60_000;
    if (priceDue) lastPriceCheck = t;

    /** Cap, route, then send (or count, in a dry run). Returns true when the alert went out or would have. */
    async function deliver(s, { key, text, kind, propertyId }, tally) {
      if ((s.outbound_count ?? BUDGET) >= BUDGET) { counts.capped += 1; return false; }
      if (!s.photon_space) { counts.noRoute += 1; return false; }
      if (!real()) { counts[tally] += 1; s.outbound_count += 1; return true; }
      const outcome = await send(s.photon_space, key, text);
      if (outcome === "no_route") { counts.noRoute += 1; return false; }
      if (outcome !== "sent") { counts.failed += 1; return false; }
      store.recordAlert(s.search_id, { kind, propertyId, simulated: true });
      store.addOutbound(s.search_id, 1);
      s.outbound_count += 1;
      counts[tally] += 1;
      return true;
    }

    for (const s of store.alertSearches()) {
      if (!allowedHashes.has(s.sender_hash)) { counts.blocked += 1; continue; }
      const age = t - Date.parse(`${s.created_at.replace(" ", "T")}Z`);
      if (!store.hasReachOut(s.search_id) && !store.hasReminder(s.search_id) && age >= afterMs) {
        await deliver(s, { key: `typecast-alert:reminder:${s.search_id}`, text: reminderText(), kind: "reach_out_reminder", propertyId: null }, "reminders");
      }
      if (!priceDue || s.max_rent == null) continue;
      for (const pick of store.picksFor(s.search_id)) {
        if (pick.rent_ref == null) continue;
        const slot = `${s.search_id}|${pick.property_id}`;
        const checkNo = checkCounts.get(slot) ?? 0;
        checkCounts.set(slot, checkNo + 1);
        const rent = rentSource(pick, { checkNo, searchId: s.search_id });
        if (rent == null) continue;
        const verdict = verdictFor(rent, s.max_rent);
        const row = getState(s.search_id, pick.property_id);
        const checkedAt = new Date(t).toISOString();
        if (!row) { putState(s.search_id, pick.property_id, { state: verdict, streak: 0, lastRent: rent, checkedAt }); continue; }
        if (verdict === row.state) { putState(s.search_id, pick.property_id, { state: row.state, streak: 0, lastRent: rent, checkedAt }); continue; }
        const streak = row.streak + 1;
        if (streak < 2) { putState(s.search_id, pick.property_id, { state: row.state, streak, lastRent: rent, checkedAt }); continue; }
        const sent = await deliver(s, {
          key: `typecast-alert:price:${s.search_id}:${pick.property_id}:${checkedAt}`,
          text: priceAlertText(pick, { rent, maxRent: s.max_rent, rentUnits: s.rent_units, verdict }),
          kind: verdict === "above" ? "price_above" : "price_back_within", propertyId: pick.property_id,
        }, "priceAlerts");
        // A blocked alert keeps the old state and a streak of 2, so it is retried on the next check.
        putState(s.search_id, pick.property_id, sent ? { state: verdict, streak: 0, lastRent: rent, checkedAt } : { state: row.state, streak: 2, lastRent: rent, checkedAt });
      }
    }
    const total = counts.reminders + counts.priceAlerts;
    if (total || counts.capped || counts.noRoute || counts.failed) {
      log(`alerts ${real() ? "sent" : "dry run, would send"}: ${counts.reminders} reminder(s), ${counts.priceAlerts} price alert(s)${counts.capped ? `; ${counts.capped} held back by the 8-message cap` : ""}${counts.noRoute ? `; ${counts.noRoute} with no route yet` : ""}${counts.failed ? `; ${counts.failed} failed` : ""}${real() ? "" : "; nothing was sent"}`);
    }
    return counts;
  }

  return { optIn, saveResults, wrapHandle, tick, hash: hashSender, isReal: real };
}
