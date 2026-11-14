# Owner 1 status

Updated 2026-11-14 10:18 UTC. Branch lane-a, PR #3 into dev.

Implemented real cosine retrieval over private CLIP embeddings, strict cache/model
validation, pre-top-k filters, cross-model/property example matching, atomic index
generation builder, bounded/resumable Matterport horizon importer, and evaluation
CLI. Estimated geometry now returns explicit unknown status with current shared
ShotFit schema. No shared schema or root dependency edits.

Verified locally: `python scripts/verify.py`: 46 tests passed and API smoke passed.
Controlled vectors cover ranking, null filters, corruption, duplicate IDs and
source exclusion. Synthetic HTTP clients cover retries, partial failure, unsafe
redirect refusal and resume. Import/build/search generation roundtrip passes.

LIVE evidence: individual sponsor keys issued for registered Typecast team;
authentication retrieved 39 panoramas for the sponsor reference model. First
catalog-linked batch downloaded 64 real horizon faces from two distinct properties;
one additional catalog model returned a GraphQL error and was reported, not faked.
All credentials and licensed artifacts remain private/ignored. CLIP dependency
installation and broader catalog ingestion are in progress, so real text/image
retrieval and quality metrics are not yet claimed.

Integration: read index/README.md. Property IDs are literal costar_property_id from
the sponsor catalog and need agreement with Owner 2's private records. Image URLs
are /cache/views/... for a team-local/private server; no public cache mount.
Cube-local headings are not compass bearings or validated SDK tour poses.
Owner 3 consolidates optional index/requirements.txt before broad team installation.

Next: finish real embeddings and query smoke, third usable property then 10-20,
room evidence enrichment, private viewer verification, and 20 human-labelled
held-out scenes. Grok Bot is auditing readiness/tests on its own computer; Gemini
is drafting pure room-boundary mapping. Claude's browser login works but quota
blocks review. Provider agreement accepted with explicit user authorization;
data/keys cannot be publicly demonstrated or committed and must be deleted after
the event. Public demo permission requires sponsor clarification.
