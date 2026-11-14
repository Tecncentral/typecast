"""Fetch room evidence for an existing private manifest; never invent directional depth."""
import argparse
import json
from pathlib import Path
import httpx
from index.build import cache_path
from index.matterport import (load_matterport_credentials, fetch_model_record,
                              atomic_write_json, MatterportIngestionError)
from index.rooms import ROOMS_GRAPHQL_QUERY, enrich_source_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    args = parser.parse_args()
    path = cache_path(args.manifest)
    source = json.loads(path.read_text(encoding='utf-8'))
    models = sorted({r['model_id'] for r in source['records']})
    auth = load_matterport_credentials()
    payloads, failed = {}, 0
    with httpx.Client() as client:
        for model_id in models:
            try:
                model = fetch_model_record(client, model_id=model_id, auth=auth,
                    query=ROOMS_GRAPHQL_QUERY, max_retries=1)
                payloads[model_id] = {'data': {'model': model}}
            except MatterportIngestionError:
                failed += 1
    result = enrich_source_manifest(source, payloads)
    atomic_write_json(path.with_name('rooms_source_manifest.json'), result)
    print(json.dumps({'models': len(models), 'failed': failed,
        'views': len(result['records']),
        'room_matched_views': sum(r['room_id'] is not None for r in result['records']),
        'ceiling_estimates': sum(r['ceiling_m'] is not None for r in result['records'])}))


if __name__ == '__main__':
    main()
