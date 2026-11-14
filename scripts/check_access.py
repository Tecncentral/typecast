"""Safe credential presence and optional read-only provider diagnostics.

--network checks model availability and Matterport/Vexcel authentication without
generation calls or printing credentials, imagery, prompts or property rows.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv


def inspect_access(network: bool = False) -> dict:
    load_dotenv(ROOT / ".env", override=False)
    names = ("LLM_API_KEY", "VISION_API_KEY", "MATTERPORT_API_KEY",
             "MATTERPORT_API_SECRET", "MATTERPORT_SDK_KEY", "VEXCEL_API_KEY",
             "LANGSMITH_API_KEY")
    result = {
        "credentials_present": {name: bool(os.getenv(name)) for name in names},
        "private_join_present": (ROOT / "cache/join.parquet").is_file(),
        "network_checked": network,
    }
    if not network:
        return result
    if os.getenv("LLM_API_KEY"):
        from openai import OpenAI
        try:
            with OpenAI(api_key=os.environ["LLM_API_KEY"], timeout=20, max_retries=0) as client:
                ids = {model.id for model in client.models.list()}
            result["openai"] = {
                "status": "ok",
                "llm_model_available": os.getenv("TYPECAST_LLM_MODEL", "") in ids,
                "vision_model_available": os.getenv("TYPECAST_VISION_MODEL", "") in ids,
            }
        except Exception as error:
            result["openai"] = {"status": "error", "kind": type(error).__name__,
                                "http_status": getattr(error, "status_code", None)}
    else:
        result["openai"] = {"status": "missing_key"}
    if os.getenv("MATTERPORT_API_KEY") and os.getenv("MATTERPORT_API_SECRET"):
        import httpx
        try:
            response = httpx.post(
                "https://api.matterport.com/api/models/graph",
                auth=(os.environ["MATTERPORT_API_KEY"], os.environ["MATTERPORT_API_SECRET"]),
                json={"query": '{ models(query: "*") { totalResults } }'}, timeout=20,
            )
            body = response.json() if response.is_success else {}
            errors = body.get("errors", [])
            result["matterport"] = {
                "http_status": response.status_code,
                "status": "ok" if response.is_success and not errors and body.get("data") else "error",
                "graphql_error_count": len(errors),
            }
        except Exception as error:
            result["matterport"] = {"status": "error", "kind": type(error).__name__}
    else:
        result["matterport"] = {"status": "missing_key_or_secret"}
    if os.getenv("VEXCEL_API_KEY"):
        import httpx
        import xml.etree.ElementTree as ET
        try:
            response = httpx.get(
                "https://api.vexcelgroup.com/v2/ortho/wmts",
                params={"api_key": os.environ["VEXCEL_API_KEY"], "SERVICE": "WMTS",
                        "REQUEST": "GetCapabilities", "VERSION": "1.0.0"}, timeout=20,
            )
            capabilities = False
            if response.is_success:
                capabilities = ET.fromstring(response.content).tag.split("}")[-1] == "Capabilities"
            result["vexcel"] = {"http_status": response.status_code,
                                "status": "ok" if capabilities else "error"}
        except Exception as error:
            result["vexcel"] = {"status": "error", "kind": type(error).__name__}
    else:
        result["vexcel"] = {"status": "missing_key"}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", action="store_true", help="Make read-only provider checks")
    print(json.dumps(inspect_access(parser.parse_args().network), indent=2))
