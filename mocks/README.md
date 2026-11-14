# mocks

Everything here is invented for building against. Addresses and ids are fake. `pick.json` and `events.jsonl` are the output of `agent/pipeline.py` on the mock data.

The 15 `img/` files are labelled synthetic placeholders generated from fixture metadata, not building photographs. Rebuild with `python scripts/make_mock_images.py`. Real frame ingestion belongs to lane A and stays under ignored `cache/`.

For a city-free scene, the API response also has this optional field (the
`notice` event in `events.jsonl` carries the same text):

```json
{"notes": ["No city named; searched Los Angeles. Name Houston to search there."]}
```

This is a response-field example, not another pick. Named-city requests return
`notes: []`; older clients may omit the field. Refinement retains the original
search-scope note because it does not search a new city pool.
