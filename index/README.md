# Owner 1: private interior retrieval

The public repository contains code and synthetic tests. All sponsor catalogs,
images, manifests, labels and embeddings belong in ignored `cache/`. `.env` is
private. Each teammate obtains their own sponsor keys with `/costar-keys` and
joins **Typecast**. Never copy credentials into prompts or GitHub.

## Run

### One-command setup for another teammate

After installing baseline and index requirements and setting private sponsor keys:

```sh
python -m index.bootstrap --max-models 20 --max-sweeps 8
```

This downloads/validates the official catalog, chooses deterministic catalog-linked
properties, resumes imagery, fetches room evidence and builds CLIP embeddings.
Use `--models cache/team-models.json` when Owner 2 supplies the agreed property
set. `--prepare-only` skips encoding. `--reuse-catalog` explicitly permits using
the cached CSV. There is no silent fixture fallback. The complete command was
verified locally against 19 available models and 608 views; one catalog model was
unavailable. Reproduction needs event-valid credentials and optional model weights.

For full available commercial coverage across Los Angeles and Houston, use the
current private exact-ID join and cached official catalog:

```sh
python -m index.bulk --workers 8 --max-sweeps 8 --multifamily 20
```

This selects one catalog model per available Office, Industrial, Flex and
GeneralRetail property, plus 20 available Multifamily properties balanced across
cities. Availability means marketed lease space under `data/SCHEMA.md`; it does
not establish filming permission. Missing model mappings and inaccessible models
are reported as uncovered. Properties with fewer than 8 source scans retain their
available scans. Existing shots, room evidence, provenance and embeddings remain
in the published index. Metadata guides apartment diversity; inspect actual
interiors before claiming visual distinctiveness.

The worker count (at most 8) also bounds simultaneous provider requests. Shared
models are downloaded and encoded once, then associated with the explicitly
supplied property pairs. Catalog disagreements remain recorded in private
provenance. Each model has its own resumable checkpoint under
`cache/matterport/bulk/`; repeating the command validates and resumes it. Encoding
reuses unchanged source views, and one complete immutable generation is published
atomically. Aggregate progress is printed; private selection and coverage reports
remain under ignored `cache/matterport/`. `--plan-only` skips provider requests and
index publication; it saves the private selection for inspection. Failed or
degraded model captures remain retryable, and a partial run publishes its usable
views with a nonzero exit status. A subsequent run repairs source/index gaps and
adds missing faces without replacing the original indexed views.
Recorded provider or transport failures cause alternate models to be preferred by
default. `--retry-failed` allows those candidates again without deleting their
private diagnostics. A successful no-change resume keeps the current generation.

The November 14 private expansion completed in 14.15 minutes: 10,568 views from
343 properties and 329 models. All 307 mapped available commercial properties and
20 available Multifamily properties are covered. Another 16 available commercial
properties have no supplied scan mapping. Seven inaccessible apartment models
were replaced with available selections; all completed captures have zero failed
faces and room requests. Exactly 302 selected properties have 8 scans; the other
25 have 1–7 catalogued scans. The original 608 Shot records and embedding floats,
source records and provenance were verified unchanged. Twenty representative
apartment interiors were visually inspected by AI; this is not human relevance
evaluation. Private evidence and contact sheets are in
`cache/matterport/bulk-review/`.

From the repository root, install the baseline lock first. CLIP is optional and
heavy; install `python -m pip install -r index/requirements.txt` for indexing and
real text search. The core tests use controlled vectors and do not download models.

Set MATTERPORT_API_KEY and MATTERPORT_API_SECRET privately in `.env` (the importer
also accepts MATTERPORT_API_TOKEN, which takes precedence when both are set). Download the
official `models_index.csv` from the sponsor quickstart into `cache/matterport/`.
Create `cache/matterport/models.json` as a JSON list of objects containing
`model_id` (catalog `sid`) and `property_id` (catalog `costar_property_id`). Use
actual catalog joins, and confirm IDs agree with Owner 2's private property table.
Homes listing identifiers require an explicit agreed mapping; they are a separate
identifier namespace. The catalog can contain models that currently deny access.

```sh
python -m index.matterport --models cache/matterport/models.json --max-models 3 --max-sweeps 8
python -m index.build cache/matterport/source_manifest.json --prepare-only
python -m index.build cache/matterport/source_manifest.json
```

For room evidence and the optional standalone interior demo:

```sh
python -m index.enrich cache/matterport/source_manifest.json
python -m index.build cache/matterport/rooms_source_manifest.json
# PowerShell: $env:TYPECAST_USE_MOCKS='0'
# macOS/Linux: export TYPECAST_USE_MOCKS=0
python -m uvicorn index.preview:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. The first query loads CLIP; subsequent queries reuse
the encoder. The preview serves only indexed images within cache/views, never
the entire cache or .env. `cache/view-provenance.json` preserves original scan
positions, face indices, source checksums, retrieval timestamps and room labels.
Direct provider anchor room/floor links take precedence; otherwise matching requires
a unique containing closed boundary and reliable floor identity. Ambiguity remains
unknown. Source rotation quaternions are retained without assuming SDK conventions.
Area and ceiling values
are provider estimates; directional depth remains unknown. The user confirmed
hackathon-demo permission; this does not put raw assets into public GitHub.

The importer uses the production GraphQL API, separates Basic credentials from
CDN requests, bounds requests/retries, verifies images, resumes valid downloads,
and reports partial failures. Zero valid shots exits nonzero. Inspect the private
manifest summary; a successful exit can include unavailable models.

The builder publishes complete immutable index generations under
`cache/shot-index/` through an atomic `CURRENT` pointer. Flat `shots.json`,
`embeddings.npy`, `manifest.json` exports are also readable. The manifest identifies
`sentence-transformers/clip-ViT-B-32`; image and text vectors use the same model.
Set `TYPECAST_USE_MOCKS=0` before starting the server for real retrieval. Missing
or corrupt indexes fail explicitly. Restart/reconfigure the process after rebuilding.

## Integration contract

Existing search_shots/get_shot/check_shot signatures and Shot schema are preserved.
Real search uses normalized image/text cosine similarity, filters before top-k,
and excludes both source model and source property for example-shot queries.
Mock mode defaults on for the shared scaffold and uses the existing fixture file;
mock ordering preserves supplied fixture scores and is not semantic quality evidence.

Image paths are `/cache/views/<shot_id>.jpg`, relative to the repo root. Owner 4
must serve these **only to the registered team in a local/private environment**;
no public static cache mount or deployment. Keys and signed CDN URLs are not in
the Shot response. The importer retains sweep position and provenance privately.

Cube faces 1-4 are already perspective images: they are never projected as 2:1
panoramas. Heading is cube-local relative direction, **not compass bearing or a
verified SDK camera pose**. The physical depth and ceiling remain unknown until
appropriate geometry is obtained. `measure_on_site=True` yields status unknown.
Do not invent tour alignment. Equirectangular imports require explicit alignment.

## Evaluation and remaining work

Write private human labels as a JSON list of `{scene, relevant_shot_ids}` and run
`TYPECAST_USE_MOCKS=0 python -m index.eval cache/labels.json`. In PowerShell set the
environment variable separately. The evaluator reports sample count, recall@10
and hit rate. Labels must precede tuning; keep held-out scenes separate. No real
quality metric has been measured merely by passing synthetic tests.

Before claiming Owner 1 complete: visually inspect actual views, index 10-20 useful
properties, verify real query ordering and cross-property matches, align property
IDs with Owner 2, verify private image rendering with Owner 4, obtain room evidence,
and evaluate 20 human-labelled scenes. Sponsor key/data expiration and deletion
requirements apply to every local/private copy.

Source: official sponsor quickstart
https://beta-app.matterport.com/2026-princeton-hackathon/quickstart .
Gemini supplied draft retrieval/importer code; local review corrected signatures,
provider status, dependency use, error redaction and cache generation compatibility.


## Camera planning studio (Owner 1 extension)
Run the preview on the SDK-permitted origin **http://localhost:8765/** (127.0.0.1 still supports search).
`python -m index.enrich cache/matterport/source_manifest.json` refreshes room evidence
and saves validated polygons in ignored `cache/matterport/room-plans.json`.
Bootstrap now saves the same polygons automatically. Current private coverage:
25 valid room polygons across 19 models; 164 indexed views have a polygon containing
their scan position. Missing boundaries remain unknown.

The preview has a varied shortlist (MMR, at most two views per property and one per
model/scan), optional mood/light/material query fields, an editable scene lookbook,
and a lens planner. The planner uses a manual heading in the API floor XY plane,
Super35 or full-frame sensor width, focal length and desired subject frame width.
It displays horizontal FOV, subject distance, first wall intersections, frame edges,
2 m actor-side and 1 m camera-side centerline clearance. These are room-boundary
estimates excluding furniture, access and rigging; `status` remains unknown.
Manual heading is independent of panorama cube heading and SDK orientation.

`/api/plan/{shot_id}?focal=24&sensor=24.9&width=3&heading=0` is an additive local
preview API; shared Shot/search/check_shot interfaces are unchanged. The SDK
connection exposes only the domain-bound browser SDK key. Source-scan navigation
requires a unique observed SDK ID match, never a guessed pose or nearest scan.
Use the original tour link if SDK access or matching fails.

Lookbooks export self-contained HTML with selected images, creative notes,
source identifiers and saved lens setup, plus editable JSON. Save before refreshing:
selection is held in the tab only. Keep licensed lookbooks within the permitted team/demo.

## Blinded relevance evaluation
Open `/evaluate`. Twenty authored visual scenes are fixed in
`index/evaluation-scenes.json` (15 test, 5 tuning). Candidate order is blinded;
reviewers mark relevant frames from the top-40 cosine pool and identify whether
the review was human or AI. Empty relevant sets are valid reviewed negatives.
Labels are private in `cache/evaluation/interior-labels.json`; no labels are seeded.
`/api/evaluation/report` exports attribution and labels.
`/api/evaluation/metrics` compares cosine and diverse pooled recall@10, separately
by human/AI, live/mock and test/tune, excluding no-relevant pools from recall while
reporting their count. Pooled recall is not exhaustive catalog recall. Freeze test
labels before tuning; never call AI or fixture labels human-held-out accuracy.

Sources: [Embed SDK quickstart](https://developers.matterport.com/embed-sdk/quickstart/),
[Sweep navigation](https://developers.matterport.com/reference/sweep/).
