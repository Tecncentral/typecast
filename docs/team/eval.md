mock run: not a result

# Retrieval evaluation

Date: 2026-11-14T09:52:53+00:00

The scene texts are authored fiction, not source data. No relevance judgments are inferred from mock scores.

Engine(s): fixed. Source mode(s): mock.

| Split | Attempted | Succeeded | Scored labels | Unlabeled | Mean recall@10 | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | 20 | 20 | 0 | 20 | N/A | 2.87 | 3.29 |
| test | 15 | 15 | 0 | 15 | N/A | 2.87 | 4.64 |
| tune | 5 | 5 | 0 | 5 | N/A | 2.88 | 3.29 |

Recall@10 is the fraction of hand-labeled relevant shot ids found in the first ten cached ranked retrieval candidates, averaged over scored scenes. Empty or absent labels are skipped, never counted as zero recall. Failed labeled requests are reported as failures and are not scored.

Latency is wall-clock time for the in-process POST /scout request, including response validation and serialization but excluding app startup. There is no warmup. p50 is the median; p95 is the nearest-rank 95th percentile. These are local measurements, not deployed network latency.

| Scene | Split | Top-k count | Recall@10 | Latency ms | Engine | Source mode | Status |
|---|---|---:|---:|---:|---|---|---|
| office-01 | test | 10 | N/A | 4.64 | fixed | mock | unlabeled; skipped |
| office-02 | test | 10 | N/A | 3.07 | fixed | mock | unlabeled; skipped |
| office-03 | test | 10 | N/A | 3.07 | fixed | mock | unlabeled; skipped |
| openplan-01 | test | 10 | N/A | 2.76 | fixed | mock | unlabeled; skipped |
| openplan-02 | test | 10 | N/A | 3.23 | fixed | mock | unlabeled; skipped |
| openplan-03 | test | 10 | N/A | 2.85 | fixed | mock | unlabeled; skipped |
| lobby-01 | test | 10 | N/A | 2.87 | fixed | mock | unlabeled; skipped |
| lobby-02 | test | 10 | N/A | 2.65 | fixed | mock | unlabeled; skipped |
| retail-01 | test | 10 | N/A | 3.01 | fixed | mock | unlabeled; skipped |
| retail-02 | test | 10 | N/A | 3.23 | fixed | mock | unlabeled; skipped |
| warehouse-01 | test | 10 | N/A | 3.13 | fixed | mock | unlabeled; skipped |
| warehouse-02 | test | 10 | N/A | 2.67 | fixed | mock | unlabeled; skipped |
| apartment-01 | test | 10 | N/A | 2.64 | fixed | mock | unlabeled; skipped |
| apartment-02 | test | 10 | N/A | 2.78 | fixed | mock | unlabeled; skipped |
| apartment-03 | test | 10 | N/A | 2.74 | fixed | mock | unlabeled; skipped |
| office-04 | tune | 10 | N/A | 2.96 | fixed | mock | unlabeled; skipped |
| openplan-04 | tune | 10 | N/A | 3.29 | fixed | mock | unlabeled; skipped |
| lobby-03 | tune | 10 | N/A | 2.88 | fixed | mock | unlabeled; skipped |
| retail-03 | tune | 10 | N/A | 2.81 | fixed | mock | unlabeled; skipped |
| warehouse-03 | tune | 10 | N/A | 2.66 | fixed | mock | unlabeled; skipped |

Labels file: `agent/eval/labels.template.jsonl`. The template intentionally has 20 empty label sets.

Before tuning, inspect the real shot corpus and hand-label relevant shots for all 20 scenes, recording the labeler. Keep licensed shot ids and judgments in an ignored private file such as `cache/eval/labels.jsonl`; do not fill the public template. Freeze the 15 test scenes and their labels. Use only the five tune scenes for development, then report test recall separately.

Reproduce the offline harness: `.venv/bin/python agent/eval/run_eval.py --mode mock`. Once authorized real data and labels exist, use `--mode live --labels cache/eval/labels.jsonl --split test`. Mock mode blanks provider keys, disables parsing/vision models and tracing, blocks sockets and isolates thread/draft files in a temporary directory.

The report contains aggregate metrics and authored scene ids only; retrieved shot ids are not published.
