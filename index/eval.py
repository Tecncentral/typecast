"""Evaluate privately labelled scenes; never manufacture a quality number."""
import argparse
import json
from index.search import search_shots

def evaluate(cases, k=10):
    if not cases or k <= 0:
        raise ValueError('Need labelled scenes and positive k')
    recalls, hits = [], []
    for case in cases:
        relevant = set(case['relevant_shot_ids'])
        if not relevant:
            raise ValueError('Every scene needs at least one human-labelled relevant shot')
        retrieved = {s.shot_id for s in search_shots(query_text=case['scene'], k=k)}
        overlap = len(relevant & retrieved)
        recalls.append(overlap / len(relevant)); hits.append(bool(overlap))
    return {'scenes': len(cases), 'k': k, 'mean_recall_at_k': sum(recalls)/len(cases),
            'hit_rate_at_k': sum(hits)/len(cases)}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('labels'); args = parser.parse_args()
    print(json.dumps(evaluate(json.loads(open(args.labels, encoding='utf-8').read())), indent=2))
