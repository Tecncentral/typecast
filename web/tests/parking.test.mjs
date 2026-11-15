import test from "node:test";
import assert from "node:assert/strict";
import {
  parkingSummary,
  vehiclesOf,
  verdictText,
  lotSource,
  recordedText,
} from "../parking.js";
import { tidyText, readableReason } from "../utils.js";

const lot = (area, extra = {}) => ({
  property: { property_id: "1", ...extra.property },
  logistics: {
    parking_status: "estimated",
    parking_area_m2: area,
    truck_spaces: 2,
    source_evidence: [{ claim: "Vexcel SAM3 segmented nearby surface-parking area" }],
    ...extra.logistics,
  },
});

test("capacity follows the backend rule: floor(area / 30), four per truck", () => {
  const summary = parkingSummary(lot(2713.8), { trucks: 5, cars: 10 });
  assert.equal(summary.capacity, 90);
  assert.equal(summary.demand, 30);
  assert.equal(summary.spare, 60);
  assert.equal(summary.fits, true);
  assert.equal(verdictText(summary), "Lot covers 5 trucks + 10 cars");
});

test("a lot too small for the new demand reports the shortfall", () => {
  const summary = parkingSummary(lot(576.5), { trucks: 5, cars: 10 });
  assert.equal(summary.capacity, 19);
  assert.equal(summary.fits, false);
  assert.equal(verdictText(summary), "Lot short by 11 car spaces");
});

test("unknown, sliver and zero-demand cases never claim a fit", () => {
  assert.equal(parkingSummary(lot(null), { trucks: 2, cars: 10 }).fits, null);
  assert.equal(
    parkingSummary(lot(900, { logistics: { parking_status: "unknown" } }), { trucks: 2, cars: 10 }).capacity,
    null,
  );
  assert.equal(parkingSummary(lot(0.1), { trucks: 2, cars: 10 }).capacity, null);
  const none = parkingSummary(lot(900), { trucks: 0, cars: 0 });
  assert.equal(none.fits, null);
  assert.equal(verdictText(none), "No crew vehicles requested");
  // Trucks alone fitting says nothing about crew cars that are unknown.
  assert.equal(parkingSummary(lot(900), { trucks: 2, cars: null }).fits, null);
});

test("vehicles come from the response, else only the truck allocation", () => {
  assert.deepEqual(vehiclesOf({ vehicles: { trucks: 5, cars: 10 } }), { trucks: 5, cars: 10, known: true });
  assert.deepEqual(vehiclesOf({ picks: [lot(900)] }), { trucks: 2, cars: null, known: false });
});

test("provenance and CoStar record are read, not inferred", () => {
  assert.equal(lotSource(lot(900)), "Vexcel-segmented");
  assert.equal(
    lotSource(lot(900, { logistics: { source_evidence: [{ claim: "OSM mapped nearby surface-parking area" }] } })),
    "OSM-mapped",
  );
  assert.equal(lotSource(lot(900, { logistics: { source_evidence: [] } })), null);
  assert.equal(
    recordedText(lot(900, { property: { parking_spaces: { Surface: 73, Covered: 129 } } })),
    "CoStar record: 73 surface + 129 covered spaces",
  );
  assert.equal(recordedText(lot(900, { property: { parking_spaces: { Surface: "x" } } })), null);
});

test("display formatting only rounds units and renames the blocker prefix", () => {
  assert.equal(tidyText("34.0644 m2 room, 2.73779 m ceiling"), "34.1 m² room, 2.7 m ceiling");
  assert.equal(tidyText("204.015 m² of hardscape"), "204 m² of hardscape");
  assert.equal(tidyText("near 29.7309649, -95.5724936"), "near 29.7309649, -95.5724936");
  assert.equal(tidyText("estimate-date: 2025-12-19T00:00:00."), "estimate-date: 2025-12-19.");
  assert.equal(
    readableReason("Blocked alternative; CoStar: office; Matterport: 941.267 m2 room; Vexcel: 2 truck"),
    "Open checks before booking (see caveats). CoStar: office; Matterport: 941 m² room; Vexcel: 2 truck",
  );
});
