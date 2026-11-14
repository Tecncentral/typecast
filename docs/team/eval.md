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
