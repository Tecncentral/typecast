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

From the repository root, install the baseline lock first. CLIP is optional and
heavy; install `python -m pip install -r index/requirements.txt` for indexing and
real text search. The core tests use controlled vectors and do not download models.

Set MATTERPORT_API_KEY and MATTERPORT_API_TOKEN privately in `.env`. Download the
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
