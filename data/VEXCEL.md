# Private Vexcel logistics

Run after building the private CoStar join and Matterport shot index:

```sh
TYPECAST_USE_MOCKS=0 python -m data.vexcel_precompute
```

This resolves every property in `cache/shot-index/CURRENT` through the exact-ID
join and saves source responses, masks, aerial images and logistics under
`cache/vexcel/<property_id>/`. Licensed records and derivatives must remain
private; never publish this cache or commit it. The Vexcel key goes only to
`api.vexcelgroup.com`, with redirects disabled. Errors omit provider bodies,
credential-bearing URLs and source rows. CLI output is aggregate coverage only.

Successful sources are reused. `--refresh` explicitly replaces them and is
required when a property's coordinates change. `--offline` derives records
without network calls or a key. On a coordinate change the complete previous
cache generation is preserved under private `cache/vexcel/.history/` before
fetching new sources; a failed refresh cannot rebind stale imagery or masks.
`--property-id` selects an explicit private ID.
`--without-osm` records a known OSM outage without repeatedly calling it. The
first OSM failure also suppresses OSM requests for the rest of that batch.
Requests are bounded and sequential. Missing sources cause a nonzero exit while
complete partial records are saved with explicit unknowns.

OSM uses `https://ovp.dresel.systems/api-na/interpreter` by default, the North
America regional extract listed in the official OSM public-instance table.
`TYPECAST_OVERPASS_URL` can explicitly select that endpoint,
`https://overpass.private.coffee/api/interpreter`, or
`https://overpass-api.de/api/interpreter`; all other destinations are rejected.
There is no automatic server rotation. The query has a 30-second execution
budget and 64 MiB server memory limit; transport has a 10-second connect and
55-second read timeout plus a 20 MiB response limit. The identifying User-Agent
links the public project. Redirects remain disabled and OSM receives no Vexcel
credentials. These public endpoints are used only for this small, sequential
private precompute, never during a scout request.

The German endpoint previously returned HTTP 406 and Private.coffee timed out.
On 2026-11-14, the same query succeeded on the documented North America
endpoint (HTTP 200, 187 elements, no partial-result remark, 2.263 seconds for
the first indexed property). This verifies query execution on that instance;
the earlier failures do not establish a query-syntax error. Query results with
a `remark` are rejected as partial. A source refresh is unnecessary to repair
missing OSM: rerun the command above without `--refresh` to reuse successful
Vexcel sources and request only missing OSM.

The completed repair cached 19/19 OSM sources (3,688 elements), with zero
provider failures or partial-result remarks. All 19 noise screens are now
estimated: six properties have proximity flags (three freeway, one rail, two
airport/runway). Parking capacity estimates increased from nine to 14 through
five actual mapped OSM parking-polygon fallbacks. All 19 walking distances
remain unknown: the sources do not establish the required connected route and
building-associated entrance. All 19 annotated aerials validate. SHA-256
comparison confirmed that all 95 successful Vexcel source files were reused
unchanged. Aggregate repair diagnostics are private in
`cache/vexcel/osm-repair-report.json`; raw OSM remains under each private
property cache.

Vexcel HTTP 403 is saved as `outside Vexcel coverage`. The property still gets
a complete partial record with unknown fields; an unavailable source never
becomes a zero capacity or a fabricated geometry.

`plan_logistics` preserves fixture behavior and reads normalized cache only in
live mode. It never waits for a provider. Missing cache raises
`VexcelUnavailable` (`FileNotFoundError`), allowing the pipeline to skip that
candidate. Missing or corrupt live sources never fall back to fixtures.

The current official schemas were read before live requests:

- [Property extract](https://api.vexcelgroup.com/v2/api-docs/property)
- [Ortho extract](https://api.vexcelgroup.com/v2/api-docs/ortho)
- [Semantic search](https://api.vexcelgroup.com/v2/api-docs/embedding)
- [Custom elements](https://api.vexcelgroup.com/v2/api-docs/custom-elements)
- [OSM Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API) and its
  [query language](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL)

The adapter requests Vexcel SAM3 parking segmentation and traces the actual
cropped PNG mask cells into geographic polygons. It unions overlapping masks,
then conservatively selects one nearby connected lot within 150 m. A detection
bounding rectangle is never used as the parking outline. A documented source
image's geographic bbox maps the cropped mask to geography; observed crop
rounding up to two pixels is accepted and remains estimated. Unexpected mask
layouts remain unknown. Actual OSM surface-parking polygons are a fallback.
Semantic search returns five nearby imagery tiles; tile footprints are never
treated as parking boundaries. Parcel hardscape area is evidence, not parking
capacity: it may include patios and other paving. Nearest parcels/buildings are
never silently equated to the requested property.

Parking area uses a local metric projection, with capacity
`floor(area_m2 / 30)` car equivalents. Each requested truck consumes four
equivalents; the remaining area is available to cars. `enough_parking` checks
`4 * trucks + cars <= capacity`, avoiding double allocation. `allocate_parking`
supports cached follow-ups without mutating source evidence. Fixture counts
retain their original behavior. Permissions, current availability, truck
clearance and unobstructed passage remain unverified.

`parking_geometry` is GeoJSON **[lon, lat]**, preserving holes. Legacy
`parking_polygon` is **[lat, lon]** and is omitted when holes cannot be expressed
accurately. The annotated aerial preserves mask holes and provider attribution.

Walking distance requires a building footprint containing the property
coordinate, an associated source entrance and a connected mapped pedestrian
route from inside the lot. A centroid-to-centroid line is never called a walk.
Missing sources leave `walk_m` null. Noise checks OSM freeways within 200 m,
rail within 300 m, and airports/runways within 3 km of the property coordinate.
A successful empty lookup does not establish quiet conditions; failed lookups
have `noise_status=unknown`. Proximity is an estimate, not a sound measurement.
CoStar parking flags remain separately marked recorded/measured evidence.

The additional dependency is `shapely==2.2.0`; Pillow, NumPy, requests,
python-dotenv and Pydantic use the shared baseline. All raw provider responses,
masks and derived geometry stay in ignored private cache.
