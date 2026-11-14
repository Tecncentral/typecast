# Retrieval evaluation

Date: 2026-11-14T19:05:52+00:00

The exact authored visual prompts and human/live judgments come from the frozen blinded lab.

Engine(s): fixed. Source mode(s): live.

The human export contains 20 complete reviews: 15 held-out test scenes and five tuning scenes. This run scores only the 15 test scenes, covering 600 reviewed scene/view pairs with 352 relevant judgments. Every review matches the exact frozen scene text, split, full candidate pool, post-freeze timestamp and immutable index fingerprint. Test labels and retrieval logic were unchanged after the reviews arrived.

| Split | Attempted | Succeeded | Scored labels | Empty judged pools | Mean recall@10 | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | 15 | 15 | 15 | 0 | 0.2706 | 14539.04 | 19692.93 |
| test | 15 | 15 | 15 | 0 | 0.2706 | 14539.04 | 19692.93 |

Recall@10 is the fraction of hand-labeled relevant shot ids found in the first ten cached ranked retrieval candidates, averaged over scored scenes. Empty or absent labels are skipped, never counted as zero recall. Failed labeled requests are reported as failures and are not scored.

Latency is wall-clock time for the in-process POST /scout request, including response validation and serialization but excluding app startup. There is no warmup. p50 is the median; p95 is the nearest-rank 95th percentile. These are local measurements, not deployed network latency.

| Scene | Split | Top-k count | Recall@10 | Latency ms | Engine | Source mode | Status |
|---|---|---:|---:|---:|---|---|---|
| interior-01 | test | 10 | 0.3030 | 19692.93 | fixed | live | scored |
| interior-02 | test | 10 | 0.1250 | 14128.92 | fixed | live | scored |
| interior-03 | test | 10 | 0.3333 | 14083.81 | fixed | live | scored |
| interior-04 | test | 10 | 0.2812 | 13938.97 | fixed | live | scored |
| interior-05 | test | 10 | 0.3478 | 11930.07 | fixed | live | scored |
| interior-06 | test | 10 | 0.2857 | 14868.39 | fixed | live | scored |
| interior-07 | test | 10 | 0.2632 | 12757.59 | fixed | live | scored |
| interior-08 | test | 10 | 0.3214 | 14539.04 | fixed | live | scored |
| interior-09 | test | 10 | 0.2143 | 15075.02 | fixed | live | scored |
| interior-10 | test | 10 | 0.2667 | 11563.01 | fixed | live | scored |
| interior-11 | test | 10 | 0.2703 | 10728.92 | fixed | live | scored |
| interior-12 | test | 10 | 0.2812 | 15718.62 | fixed | live | scored |
| interior-13 | test | 10 | 0.2105 | 14905.33 | fixed | live | scored |
| interior-14 | test | 10 | 0.2941 | 18103.81 | fixed | live | scored |
| interior-15 | test | 10 | 0.2609 | 17040.05 | fixed | live | scored |

These are judgments of a frozen global top-40 cosine pool, not exhaustive catalog relevance. The /scout pipeline filters retrieval by the parsed city (Los Angeles by default) and may rerank candidates. This measures pooled pipeline recall@10, not global CLIP retrieval accuracy. Relevant views outside the city pool remain in the denominator; the diagnostic below shows this eligibility mismatch. Empty selections are complete reviews with no relevant views in the judged pool and are skipped for recall.

| Scene | Parsed city | Reviewed pool | Relevant gold | City-eligible gold |
|---|---|---:|---:|---:|
| interior-01 | Los Angeles | 40 | 33 | 20 |
| interior-02 | Los Angeles | 40 | 8 | 1 |
| interior-03 | Los Angeles | 40 | 24 | 16 |
| interior-04 | Los Angeles | 40 | 32 | 21 |
| interior-05 | Los Angeles | 40 | 23 | 14 |
| interior-06 | Los Angeles | 40 | 28 | 16 |
| interior-07 | Los Angeles | 40 | 19 | 12 |
| interior-08 | Los Angeles | 40 | 28 | 17 |
| interior-09 | Los Angeles | 40 | 14 | 4 |
| interior-10 | Los Angeles | 40 | 15 | 10 |
| interior-11 | Los Angeles | 40 | 37 | 30 |
| interior-12 | Los Angeles | 40 | 32 | 20 |
| interior-13 | Los Angeles | 40 | 19 | 16 |
| interior-14 | Los Angeles | 40 | 17 | 9 |
| interior-15 | Los Angeles | 40 | 23 | 6 |

Labels file: `cache/evaluation/agent/labels.jsonl`. Reviewer provenance, reviewed pools and frozen index fingerprints remain in ignored private JSONL files.

Keep test judgments frozen and use only tune scenes for development. Reproduce with the same exported `--scenes` and `--labels`, `--mode live --split test`, and the frozen `--index-dir`. Index changes or stale/AI/mock reviews are rejected.

## Interpretation and observed execution

The exact macro mean is **0.2705817769658798**. Across the 15 scenes, the first-ten candidate sets recover 99 human-positive scene/view pairs. The headline score averages each scene's own recall; it is not the pooled ratio 99/352 and is not a precision or general accuracy percentage.

The reviewed pools contain 8–37 relevant views per scene. Ten returned views cannot recover more than ten positives: even perfect selection across both cities would cap the mean recall at **0.4814** for these labels. All parsed cities were Los Angeles, leaving 212 city-eligible positives and 140 Houston positives in the unchanged denominator; that city constraint lowers the mathematical ceiling to **0.3790**. These ceilings explain the metric's limits and do not replace the observed score. Judgments cover only the sampled global top-40 pools; views outside those pools are unjudged.

The configured visual reranker reorders only the existing first ten candidates. Recall@10 measures membership of that set, so it does not assess ordering within those ten or the final three property cards. The 15 scenes have one human reviewer, and no claim of exhaustive catalog relevance or reviewer agreement is made.

Application revision: `cf716c1` (PR #19). Both parser and vision model were `gpt-6.1-sol`, with medium reasoning effort. Model parsing succeeded on all 15 scenes; all 150 requested vision scores were freshly computed, with zero cached scores, zero scoring failures and zero fallback events. Each scene ran once, without a warmup or retries. The first request includes lazy model initialization. Source imagery, index and logistics were already cached locally.

LangSmith tracing was enabled. Thirteen responses contained trace URLs; `interior-14` and `interior-15` returned null links after bounded trace verification. Their real scouting requests still succeeded and remain included in both retrieval and latency results. No failed trace diagnostic was retried to replace a measurement.

The unchanged evaluation CLI ran with a private observation-only wrapper recording raw responses, exact top-ten candidates and per-scene rows. Independent recomputation matched every numerator, denominator and the macro mean. Private evidence and input/code SHA-256 fingerprints are in `cache/evaluation/runs/20261114T190213Z/`; the unmodified human export is retained under `cache/evaluation/imports/`. These files, source identifiers, images and credentials remain ignored by Git. The complete repository gate passed 291 tests plus smoke, streaming/refinement/local-draft and mock-evaluation checks; the published metric above comes from the separate live run.

To reproduce, provision the private frozen index, source caches, exported labels and model credentials, and set `TYPECAST_INDEX_DIR` to the same immutable reviewed generation:

```bash
TYPECAST_ENABLE_MODEL_PARSE=1 TYPECAST_ENABLE_VISION_RERANK=1 \
  TYPECAST_ALLOW_VISION_UPLOAD=1 LANGSMITH_TRACING=true \
  TYPECAST_LLM_PROVIDER=openai TYPECAST_LLM_MODEL=gpt-6.1-sol \
  TYPECAST_VISION_MODEL=gpt-6.1-sol TYPECAST_REASONING_EFFORT=medium \
  .venv/bin/python agent/eval/run_eval.py --mode live --split test --engine fixed \
  --scenes cache/evaluation/agent/scenes.jsonl --labels cache/evaluation/agent/labels.jsonl \
  --index-dir "$TYPECAST_INDEX_DIR" --output docs/team/eval.md
```

The command regenerates the metric tables; this execution audit describes the retained first run. A later run can reuse visual scores and have different latency. Keep its results separate from this measurement.

## v1 supplemental precision (existing frozen run; no rerun)

The original v1 result above remains unchanged. Its retained first-ten results
contain **99 human-positive views in 150 returned scene/view slots**, so
**precision@10 lower bound = 0.6600 (66.00%)**. Each scene returned ten views,
so the macro precision equals that pooled ratio. Of the 150 slots, 148 were in
the reviewed pools: 99 selected as relevant and 49 not selected. The remaining
two were unjudged, and both count as misses for this conservative lower bound.

This uses the same single reviewer and frozen global top-40 candidate pools.
It does not establish that unjudged views are irrelevant, exhaustive catalog
relevance, or agreement between reviewers. No model request or retrieval rerun
was used to calculate this additional metric.

## Tune experiments

Job 5 evaluates only the five frozen tuning scenes. The 15 test scenes remain
excluded from configuration selection. The experiment reserves an image budget
before each provider request, uses a fresh private vision cache for each
attempt, records both requested and actual engines, and stops after the first
rate-limit response or at 16:30 Eastern on November 14. Maximum tuning budget:
1,000 image scorings, including images in failed calls and provider fallbacks.

Predeclared selection rule: compare precision@10 lower bound first, then
macro recall@10, against N=10/concurrency=5/per-image scoring. A proposed
default must complete all five tuning scenes on both engines, with all
requested visual scores and no engine fallback, and every deep request under
75 seconds. Canary trials can screen settings but cannot by themselves select
a default. The 90-second runtime fallback remains unchanged. No repeat test
run is permitted unless the default changes; any such result is v2, explicitly
informed by v1, and cannot replace the original report above.

### Measured configurations

| N / concurrency / batch | Engine | Scenes | P@10 lower bound | Macro R@10 | Median / max seconds | Vision calls / images |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 10/5/1 | fixed | 5 | 0.3600 | 0.3441 | 20.225 / 20.453 | 50 / 50 |
| 10/5/1 | deep | 5 | 0.3600 | 0.3441 | 53.597 / 58.911 | 50 / 50 |
| 20/5/1 | fixed | 5 | 0.3800 | 0.3524 | 24.254 / 25.326 | 100 / 100 |
| 20/5/1 | deep | 5 | 0.3600 | 0.3460 | 57.569 / 58.985 | 100 / 100 |
| 20/5/5 | fixed | 5 | 0.3800 | 0.3543 | 21.218 / 23.353 | 20 / 100 |
| 20/5/5 | deep | 5 | 0.3600 | 0.3460 | 50.597 / 55.494 | 20 / 100 |
| 20/10/1 | fixed | 1 | 0.5000 | 0.1613 | 19.303 / 19.303 | 20 / 20 |
| 20/10/1 | deep | 1 | 0.5000 | 0.1613 | 53.249 / 53.249 | 20 / 20 |
| 20/5/10 | fixed | 1 | 0.5000 | 0.1613 | 25.086 / 25.086 | 2 / 20 |
| 20/5/10 | deep | 1 | 0.5000 | 0.1613 | 55.536 / 55.536 | 2 / 20 |
| 30/10/1 | fixed | 1 | 0.5000 | 0.1613 | 24.553 / 24.553 | 30 / 30 |
| 30/10/1 | deep | 1 | 0.5000 | 0.1613 | 52.334 / 52.334 | 30 / 30 |
| 30/5/5 | fixed | 1 | 0.4000 | 0.1290 | 24.611 / 24.611 | 6 / 30 |
| 30/5/5 | deep | 1 | 0.4000 | 0.1290 | 59.831 / 59.831 | 6 / 30 |
| 40/10/1 | fixed | 1 | 0.5000 | 0.1613 | 25.182 / 25.182 | 40 / 40 |
| 40/10/1 | deep | 1 | 0.5000 | 0.1613 | 51.016 / 51.016 | 40 / 40 |
| 40/5/10 | fixed | 1 | 0.4000 | 0.1290 | 22.448 / 22.448 | 4 / 40 |
| 40/5/10 | deep | 1 | 0.4000 | 0.1290 | 53.809 / 53.809 | 4 / 40 |

### Protocol, timing scope and selection

Completed 2026-11-14 at 20:40 UTC, before the 16:30 Eastern experiment cutoff. Baseline used all five tune scenes on both engines. Eight alternatives were screened on `interior-16`, then the two strongest candidates were completed on the remaining four tune scenes. This is a budgeted screen, not an exhaustive factorial experiment. The frozen 15 test scenes were excluded from selection. Rows with five scenes cover `interior-16` through `interior-20`; one-scene rows are screening results only. Their quality averages are not directly comparable. The first three configurations include their screening requests once.

Quality is the equal-weight mean of the fixed and deep five-scene macro scores: precision lower bound first, then macro recall; a remaining tie prefers lower maximum deep latency. All requested scores must be fresh, without fallback, and every qualifying deep request must finish below 75 seconds.

Both models were `gpt-6.1-sol`; parser/vision/director reasoning was medium and delegate reasoning low. Each request had a fresh worker and isolated, empty vision cache. Request latency includes lazy CLIP initialization, model calls, tracing verification and serialization; it excludes process/app import startup. Source imagery, the frozen index and logistics were already local. These are uncached-vision local API timings, not fully cold source acquisition or deployed network timings. With five observations, nearest-rank p95 equals the maximum. Warm rehearsals and v1's single-process test have different initialization costs.

The experiment used **42 requests, 860 fresh image scorings, 544 vision provider calls and 42 parser calls**. Every request succeeded with its requested engine and all requested scores: zero cache hits, scoring failures, engine fallbacks, duplicate attempts or observed rate limits. The budget counts every submitted image, rather than treating one ten-image batch as one image. Deep-agent text calls are additional; early workers lacked complete SDK HTTP telemetry, so no complete deep-text call total is claimed. All attempts remain in the evidence.

**Selected default: 20 candidates / concurrency 5 / batch size 5.** Equal-engine tune precision lower bound is **0.3700**, versus **0.3600** at 10/5/1; macro recall is **0.35014267990074444**, versus **0.3440942928039702**. The 20/5/1 alternative ties precision at 0.3700 but has lower macro recall, 0.34920181968569064. The selected setting's slowest deep request was **55.494 s**, below the 75 s gate. It uses four vision requests for twenty images per uncached scout, versus ten requests for ten images at baseline. The latency difference is observed in this sample, not a general speed guarantee.

The advantage is small: one additional judged-positive return across 100 tune slots across both engines. This is one attempt per scene/configuration, one human reviewer and pooled global labels. No statistical significance, exhaustive relevance or final-card improvement is established. Larger pools can promote unjudged city-eligible views from outside the global judged pool, which this conservative metric counts as misses. No city filter changed.

Private protocol, budget ledger, raw responses, top-ten memberships, score caches, selection arithmetic and input/code fingerprints remain in `cache/experiments/rerank-v2/`. Cancellation handling and SDK HTTP instrumentation were corrected during baseline execution; no cancellation, 429 or scoring failure was observed, and all image reservations/vision events were present. A duplicate-aggregation correction completed during screening; there were no duplicates and it did not change these scores. Original revision fingerprints and the boundary explanation are retained privately.

The published v1 block above remains byte-for-byte unchanged. Its historical reproduction command records the original destination; any new run must use a separate `--output cache/evaluation/<new-report>.md` path. The changed default requires exactly one separately labeled v2 test pass, followed by demo warming; neither result may be used for further tuning in this job.
