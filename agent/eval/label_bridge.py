"""Freeze local blinded pools before review; export human/live labels to private JSONL.

Freeze uses the lab's local CLIP top-40 pool, never a paid model. Restart the lab
with its printed TYPECAST_INDEX_DIR before collecting fresh human judgments.
These labels measure pooled relevance, not exhaustive catalog recall.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
POOL_SCOPE = "global_top40_cosine_pool"
INDEX_FILES = ("manifest.json", "shots.json", "embeddings.npy")


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def _pool_digest(scene: dict, ids: list[str]) -> str:
    return _digest({key: scene[key] for key in ("id", "scene", "split")} | {"shot_ids": sorted(ids)})


def _timestamp(value, context: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed
    except (AttributeError, TypeError, ValueError):
        pass
    raise ValueError(f"{context}: timezone-aware timestamp required")


def _ids(value, context: str, *, allow_empty=False) -> list[str]:
    if (not isinstance(value, list) or (not value and not allow_empty)
            or any(not isinstance(item, str) or not item.strip() for item in value)
            or len(value) != len(set(value)) or len(value) > 40):
        raise ValueError(f"{context}: expected unique shot ids, at most 40")
    return value


def _scenes(value) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ValueError("Scenes must be a nonempty JSON list")
    identifiers = set()
    for scene in value:
        if (not isinstance(scene, dict) or not isinstance(scene.get("id"), str)
                or not scene["id"].strip() or scene["id"] in identifiers
                or scene.get("split") not in ("test", "tune")
                or not isinstance(scene.get("scene"), str) or not scene["scene"].strip()):
            raise ValueError("Scenes need unique ids, exact text and test/tune splits")
        identifiers.add(scene["id"])
    return value


def index_identity(index_dir: Path) -> tuple[Path, dict]:
    """Resolve CURRENT once and hash every retrieval artifact without loading models."""
    directory = index_dir.resolve()
    pointer = directory / "CURRENT"
    if pointer.exists():
        generation = pointer.read_text(encoding="utf-8").strip()
        if len(generation) != 32 or any(c not in "0123456789abcdef" for c in generation):
            raise ValueError("Invalid index generation pointer")
        directory = directory / generation
    hashes = {}
    for name in INDEX_FILES:
        path = directory / name
        if not path.is_file():
            raise ValueError(f"Index artifact missing: {name}")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[name] = digest.hexdigest()
    return directory, {"sha256": _digest(hashes), "files": hashes}


def freeze(scenes: list[dict], index_dir: Path) -> tuple[dict, Path]:
    from index.search import ShotRetrievalIndex

    directory, identity = index_identity(index_dir)
    index = ShotRetrievalIndex.from_cache_dir(directory)
    frozen = []
    for scene in _scenes(scenes):
        ids = [shot.shot_id for shot in index.search_shots(query_text=scene["scene"], k=40)]
        ids.sort(key=lambda sid: hashlib.sha256((scene["id"] + sid).encode()).hexdigest())
        frozen.append({"id": scene["id"], "scene": scene["scene"], "split": scene["split"],
                       "pool_shot_ids": _ids(ids, scene["id"]), "pool_sha256": _pool_digest(scene, ids)})
    if index_identity(directory)[1] != identity:
        raise ValueError("Index changed while freezing; publish an immutable generation first")
    return {"schema_version": 1, "mode": "live", "pool_scope": POOL_SCOPE,
            "frozen_at": datetime.now(timezone.utc).isoformat(), "index": identity,
            "scenes": frozen}, directory


def _snapshot(snapshot: dict) -> list[dict]:
    if (not isinstance(snapshot, dict) or snapshot.get("schema_version") != 1
            or snapshot.get("mode") != "live" or snapshot.get("pool_scope") != POOL_SCOPE):
        raise ValueError("Expected a live blinded-pool snapshot from label_bridge freeze")
    _timestamp(snapshot.get("frozen_at"), "Snapshot")
    identity = snapshot.get("index")
    files = identity.get("files") if isinstance(identity, dict) else None
    if (not isinstance(files, dict) or set(files) != set(INDEX_FILES)
            or any(not isinstance(value, str) or len(value) != 64
                   or any(c not in "0123456789abcdef" for c in value) for value in files.values())
            or identity.get("sha256") != _digest(files)):
        raise ValueError("Snapshot has an invalid index fingerprint")
    scenes = _scenes(snapshot.get("scenes"))
    for scene in scenes:
        ids = _ids(scene.get("pool_shot_ids"), scene["id"])
        if scene.get("pool_sha256") != _pool_digest(scene, ids):
            raise ValueError(f"{scene['id']}: frozen scene/pool fingerprint mismatch")
    return scenes


def read_lab_labels(payload) -> dict[str, dict]:
    """Accept the native scene-id mapping or the browser's /report download."""
    if isinstance(payload, dict) and "labels" in payload:
        payload = payload["labels"]
    if isinstance(payload, dict):
        for identifier, record in payload.items():
            if not isinstance(record, dict) or record.get("scene_id") != identifier:
                raise ValueError("Lab label keys must match each scene_id")
        payload = list(payload.values())
    if not isinstance(payload, list):
        raise ValueError("Expected native lab labels or a lab report export")
    labels = {}
    for record in payload:
        identifier = record.get("scene_id") if isinstance(record, dict) else None
        if not isinstance(identifier, str) or not identifier or identifier in labels:
            raise ValueError("Lab labels require unique scene_id values")
        labels[identifier] = record
    return labels


def _validate_label(scene: dict, label: dict, metadata: dict) -> None:
    identifier = scene["id"]
    if label.get("reviewer_kind") != "human" or label.get("mode") != "live":
        raise ValueError(f"{identifier}: only actual human reviews of live images are accepted")
    if not isinstance(label.get("reviewer"), str) or not label["reviewer"].strip():
        raise ValueError(f"{identifier}: actual reviewer attribution is required")
    if label.get("scene") != scene["scene"] or label.get("split") != scene["split"]:
        raise ValueError(f"{identifier}: stale scene text or split")
    reviewed = _ids(label.get("reviewed_shot_ids"), f"{identifier} reviewed pool")
    relevant = _ids(label.get("relevant_shot_ids"), f"{identifier} relevant labels", allow_empty=True)
    if set(reviewed) != set(metadata["pool_shot_ids"]) or not set(relevant) <= set(reviewed):
        raise ValueError(f"{identifier}: stale/incomplete pool or unknown relevant shot ids")
    if _timestamp(label.get("labelled_at"), identifier) < _timestamp(metadata["frozen_at"], "Snapshot"):
        raise ValueError(f"{identifier}: review predates the frozen pool; review it again")


def export(snapshot: dict, lab_labels, index_dir: Path, *, split="test") -> tuple[list[dict], list[dict]]:
    scenes = _snapshot(snapshot)
    if index_identity(index_dir)[1] != snapshot["index"]:
        raise ValueError("Current index differs from frozen generation; collect a new frozen review")
    labels = read_lab_labels(lab_labels)
    known = {scene["id"]: scene for scene in scenes}
    if set(labels) - set(known):
        raise ValueError("Labels contain unknown scene ids")
    selected = [scene for scene in scenes if split == "all" or scene["split"] == split]
    if not selected or any(scene["id"] not in labels for scene in selected):
        raise ValueError("Every selected scene needs a complete human review, including empty selections")
    for scene in selected:
        _validate_label(scene, labels[scene["id"]], {**scene, "frozen_at": snapshot["frozen_at"]})
    output_scenes, output_labels = [], []
    for scene in selected:
        metadata = {key: snapshot[key] for key in ("schema_version", "mode", "pool_scope", "frozen_at", "index")}
        metadata["pool_shot_ids"] = scene["pool_shot_ids"]
        metadata["pool_sha256"] = scene["pool_sha256"]
        output_scenes.append({key: scene[key] for key in ("id", "scene", "split")} | {"evaluation": metadata})
        label = labels[scene["id"]]
        output_labels.append({**label, "id": scene["id"], "labeler": label["reviewer"]})
    return output_scenes, output_labels


def validate_live_inputs(scenes: list[dict], labels: dict, index_dir: Path) -> Path:
    """Validate exported provenance; the caller skips this for legacy diagnostics."""
    directory, identity = index_identity(index_dir)
    for scene in scenes:
        metadata = scene.get("evaluation")
        if not isinstance(metadata, dict):
            raise ValueError("Mixed or missing frozen evaluation metadata")
        _snapshot({**metadata, "scenes": [{**scene, "pool_shot_ids": metadata.get("pool_shot_ids"),
                                          "pool_sha256": metadata.get("pool_sha256")}]})
        if metadata["index"] != identity:
            raise ValueError("Live index differs from frozen human-reviewed generation")
        label = labels.get(scene["id"])
        if label is None:
            raise ValueError(f"{scene['id']}: missing complete human review")
        _validate_label(scene, label, metadata)
        if label.get("scene_id") != scene["id"] or label.get("labeler") != label["reviewer"]:
            raise ValueError(f"{scene['id']}: exported reviewer/scene provenance mismatch")
    return directory


def _write_outputs(outputs: list[tuple[Path, str]]) -> None:
    private = {path.resolve(): text for path, text in outputs}
    if len(private) != len(outputs):
        raise ValueError("Output paths must be distinct")
    for path, text in private.items():
        if not path.is_relative_to((ROOT / "cache").resolve()):
            raise ValueError("Evaluation snapshots and labels must stay under ignored cache/")
        if path.exists() and path.read_text(encoding="utf-8") != text:
            raise ValueError(f"Refusing to overwrite frozen evaluation file: {path.name}")
    for path, text in private.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)


def main(argv=None) -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freezer = commands.add_parser("freeze", help="freeze pools before fresh human review")
    freezer.add_argument("--scenes", type=Path, default=ROOT / "index/evaluation-scenes.json")
    freezer.add_argument("--output", type=Path, default=ROOT / "cache/evaluation/frozen-pools.json")
    exporter = commands.add_parser("export", help="export complete human/live lab labels")
    exporter.add_argument("--snapshot", type=Path, default=ROOT / "cache/evaluation/frozen-pools.json")
    exporter.add_argument("--labels", type=Path, default=ROOT / "cache/evaluation/interior-labels.json")
    exporter.add_argument("--split", choices=("all", "test", "tune"), default="test")
    exporter.add_argument("--output-dir", type=Path, default=ROOT / "cache/evaluation/agent")
    for command in (freezer, exporter):
        command.add_argument("--index-dir", type=Path,
                             default=Path(os.getenv("TYPECAST_INDEX_DIR", str(ROOT / "cache/shot-index"))))
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            if args.output.exists() or not args.output.resolve().is_relative_to((ROOT / "cache").resolve()):
                raise ValueError("Choose a new private snapshot path under ignored cache/")
            snapshot, directory = freeze(json.loads(args.scenes.read_text(encoding="utf-8")), args.index_dir)
            _write_outputs([(args.output, json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n")])
            print(f"Frozen {len(snapshot['scenes'])} live pools. Restart lab with TYPECAST_INDEX_DIR={directory}")
            print(f"Snapshot: {args.output.resolve()}")
        else:
            scenes, labels = export(json.loads(args.snapshot.read_text(encoding="utf-8")),
                                    json.loads(args.labels.read_text(encoding="utf-8")), args.index_dir, split=args.split)
            paths = [args.output_dir / name for name in ("scenes.jsonl", "labels.jsonl")]
            _write_outputs([(path, "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records))
                            for path, records in zip(paths, (scenes, labels))])
            print(f"Exported {len(scenes)} complete human/live {args.split} reviews; pooled relevance only")
            for path in paths:
                print(path.resolve())
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
