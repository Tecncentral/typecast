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
without network calls or a key. `--property-id` selects an explicit private ID.
`--without-osm` records a known OSM outage without repeatedly calling it. The
first OSM failure also suppresses OSM requests for the rest of that batch.
Requests are bounded and sequential. Missing sources cause a nonzero exit while
complete partial records are saved with explicit unknowns.

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
