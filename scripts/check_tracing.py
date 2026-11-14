"""Check a running mock API's real SSE flow and fetch its LangSmith trace.

The server may call its configured model. This diagnostic prints only public
configuration booleans, timings, counts and the client-verified run URL.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from langsmith import Client

ROOT = Path(__file__).resolve().parents[1]
SCENE = ("INT. 1980s POLICE STATION, NIGHT. Big open room, drop ceiling, "
         "windows on one wall. Parking for 3 trucks and 30 crew cars.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--expected-engine", required=True, choices=["fixed", "deep"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    base = args.base_url.rstrip("/")
    with httpx.Client(timeout=120) as http:
        response = http.get(f"{base}/config")
        response.raise_for_status()
        config = response.json()
        assert set(config) == {"mode", "engine", "tracing", "matterport_sdk_key"}
        assert config["mode"] == "mock", "This diagnostic uses fixture scenes and expects mock mode"
        assert config["engine"] == args.expected_engine and config["tracing"]
        leaked = [name for name, value in os.environ.items()
                  if name != "MATTERPORT_SDK_KEY" and name.endswith(("_KEY", "_SECRET"))
                  and value and value in response.text]
        assert not leaked, f"Unexpected credential values for names: {leaked}"
        started, first_event = perf_counter(), None
        count, result, block, delegates = 0, None, {}, []
        with http.stream("GET", f"{base}/scout/stream", params={"scene": SCENE}) as stream:
            stream.raise_for_status()
            for line in stream.iter_lines():
                if line:
                    name, separator, value = line.partition(":")
                    if separator:
                        block[name] = value.lstrip()
                    continue
                if "event" not in block:
                    continue
                elapsed = perf_counter() - started
                data = json.loads(block["data"])
                if block["event"] == "agent":
                    count += 1
                    first_event = elapsed if first_event is None else first_event
                    if data["type"] in {"subagent_start", "subagent_result"}:
                        delegates.append({"type": data["type"], "agent": data["agent"],
                                          "elapsed_s": elapsed, "engine": data["engine"]})
                elif block["event"] == "result":
                    result = data
                elif block["event"] == "error":
                    raise RuntimeError("API emitted a terminal scouting error")
                block = {}
        elapsed = perf_counter() - started
    assert result and result["engine"] == args.expected_engine and result["source_mode"] == "mock"
    assert first_event is not None and first_event < elapsed
    if not result["trace_url"]:
        raise RuntimeError(f"No verified trace URL returned after {elapsed:.3f} s; check the API's trace event")
    # The SDK's returned URL contains the run id; read it back independently.
    run_id = urlparse(result["trace_url"]).path.rstrip("/").split("/")[-1]
    with closing(Client(api_key=os.environ["LANGSMITH_API_KEY"], timeout_ms=5000)) as client:
        run = client.read_run(run_id, load_child_runs=True)
        assert run.end_time is not None and run.parent_run_id is None
        assert client.get_run_url(run=run, project_name=os.getenv("LANGSMITH_PROJECT", "typecast")) == result["trace_url"]
        children, stack = [], list(run.child_runs or [])
        while stack:
            child = stack.pop()
            children.append(child)
            stack.extend(child.child_runs or [])
        assert all(not span.inputs and not span.outputs for span in [run, *children])
        if args.expected_engine == "deep":
            assert any(span.run_type == "llm" for span in children)
            assert any(span.run_type == "tool" for span in children)
    summary = {"engine": result["engine"], "source_mode": "mock", "picks": len(result["picks"]),
               "elapsed_s": elapsed, "first_event_s": first_event, "event_count": count,
               "trace_url": result["trace_url"], "trace_verified": True,
               "trace_run_id": str(run.id), "nested_spans": len(children),
               "payloads_redacted": True, "config_secret_leak": False,
               "sdk_key_present": bool(config["matterport_sdk_key"]), "delegates": delegates}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
