# Retrieval evaluation

Updated: 2026-11-14 17:20 UTC

The expanded index has 10,568 views across 343 properties. Its 15 test scenes and five tuning scenes are frozen against an immutable index generation and blinded global top-40 candidate pools.

| Held-out test status | Count / value |
| --- | ---: |
| Authored test scenes | 15 |
| Saved human test reviews | 0 |
| Scored human test scenes | 0 |
| Mean recall@10 | N/A — awaiting human review |

The live labeling lab is available at `http://localhost:8765/evaluate`. Inspect all 40 candidates per test scene, enter the actual reviewer name, keep **Human review** selected, select every relevant view, and save the complete review. An empty relevance selection is valid after inspection; it is excluded from recall and reported separately. No AI judgments have been substituted for human labels. Older labels from the 608-view index do not establish accuracy for this expanded pool.

After all 15 test reviews are saved, use the immutable generation printed by the already-created private freeze snapshot for `TYPECAST_INDEX_DIR`:

```bash
python agent/eval/label_bridge.py export --split test --index-dir "$TYPECAST_INDEX_DIR"
TYPECAST_ENABLE_MODEL_PARSE=1 TYPECAST_ENABLE_VISION_RERANK=1 \
  TYPECAST_ALLOW_VISION_UPLOAD=1 python agent/eval/run_eval.py --mode live --split test \
  --scenes cache/evaluation/agent/scenes.jsonl --labels cache/evaluation/agent/labels.jsonl \
  --index-dir "$TYPECAST_INDEX_DIR" --output docs/team/eval.md
```

The bridge rejects incomplete, stale, AI/mock or changed-index reviews. The evaluator checks the index before and after scoring. Its recall@10 measures relevant human judgments found among the pipeline's first ten ranked candidates, averaged over scored test scenes. Judgments cover the frozen global pool; the pipeline applies a parsed city filter, so the report also discloses city-eligible relevant counts. This is pooled pipeline recall, with explicit sampling limits. Keep test judgments frozen and use only the five tune scenes for development.

The [live demo latency checks](status-lane-c.md) passed both engines with real models and sources. Those authored demo checks establish execution, timing and evidence behavior; the human relevance metric above remains pending.
