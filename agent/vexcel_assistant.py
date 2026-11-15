"""Ask about a place: a language model answers with live Vexcel data through Vexcel's MCP server.

This server is the MCP client (https://api.vexcelgroup.com/v2/mcp, key in the query string to Vexcel's
own host only); the model never sees the key and never talks to Vexcel itself. It may call only a
read-only allowlist of data tools, and every call is checked first: geometry must stay within ~2 km of
the selected place, buffers and record counts are clamped (Vexcel requests are billable), and at most
MAX_CALLS tools run per question. Answers list the tools that were called so the evidence is visible.
"""
from __future__ import annotations

import json
import os
import re
import threading

import requests

MCP_URL = "https://api.vexcelgroup.com/v2/mcp"
# Each allowed tool exposes only the parameters a place question needs: given every optional filter, a
# model tends to fill them all in (pool=false, a roof material, date ranges) and the query returns nothing.
_GEO = ("wkt", "buffer-meter")
PARAMS = {
    "dtm_elevation": ("wkt",), "dsm_elevation": ("wkt",),
    "embedding_extract": ("search-text", *_GEO, "total-records"),
    "property_metadata_extract": (*_GEO, "total-records", "include", "pool", "automobile", "boat",
                                  "sport-court", "playground", "deck"),
    "property_metadata_count": (*_GEO, "pool", "automobile", "boat", "sport-court", "playground", "deck"),
    "structure_metadata_extract": (*_GEO, "total-records", "include", "roof-solar"),
    "oriented_imagery_query": ("wkt", "product-type", "include", "total-records"),
    "ortho_estimate_dates": ("wkt",),
    "oriented_imagery_collections": ("wkt",), "ortho_imagery_collections": ("wkt",),
    "structure_coverage_collections": ("wkt",), "property_coverage_collections": ("wkt",),
    "elements_detect": (*_GEO, "model-input"),
}
ALLOWED = set(PARAMS)
MAX_CALLS = 5
MAX_RESULT_CHARS = 6000
NEAR_DEG = 0.02  # ~2 km
_COORD = re.compile(r"(-?\d{1,3}(?:\.\d+)?)\s+(-?\d{1,2}(?:\.\d+)?)")


class AssistantError(RuntimeError):
    """Sanitized: never carries the key or provider bodies."""


class VexcelMCP:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("VEXCEL_API_KEY")
        if not self.api_key:
            raise AssistantError("Vexcel key missing")
        self.session_id = None
        self.http = requests.Session()
        self._lock = threading.Lock()
        self._id = 0
        self.tools: list[dict] = []

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        body = {"jsonrpc": "2.0", "method": method, **({"params": params} if params is not None else {})}
        if not notify:
            with self._lock:
                self._id += 1
                body["id"] = self._id
        try:
            r = self.http.post(MCP_URL, params={"api_key": self.api_key}, headers=headers, json=body,
                               timeout=(10, 90), allow_redirects=False)
        except requests.RequestException as error:
            raise AssistantError(f"Vexcel MCP network failure ({type(error).__name__})") from None
        if r.status_code >= 300:
            raise AssistantError(f"Vexcel MCP HTTP {r.status_code}")
        self.session_id = r.headers.get("mcp-session-id", self.session_id)
        if notify or not r.content:
            return None
        if "event-stream" in r.headers.get("content-type", ""):
            data = [json.loads(line[5:]) for line in r.text.splitlines() if line.startswith("data:")]
            message = next((d for d in data if d.get("id") == body.get("id")), data[-1] if data else {})
        else:
            message = r.json()
        if "error" in message:
            raise AssistantError(f"Vexcel MCP error: {str(message['error'].get('message', ''))[:160]}")
        return message.get("result")

    def connect(self) -> list[dict]:
        self._rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "typecast", "version": "1.0"}})
        self._rpc("notifications/initialized", notify=True)
        self.tools = [t for t in (self._rpc("tools/list") or {}).get("tools", []) if t.get("name") in ALLOWED]
        return self.tools

    def call(self, name: str, arguments: dict) -> str:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments}) or {}
        parts = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(f"[{item.get('type', 'content')} omitted]")
        text = "\n".join(parts) if parts else json.dumps(result)[:MAX_RESULT_CHARS]
        return text.replace(self.api_key, "[key]")[:MAX_RESULT_CHARS]


def guard(name: str, arguments: dict, lat: float, lon: float) -> dict:
    """Reject far-away geometry and clamp cost-driving parameters before any Vexcel call."""
    if name not in ALLOWED:
        raise AssistantError(f"Tool {name} is not allowed here")
    # Unknown parameters and false-valued filters are dropped: a filter is only meaningful when asked for.
    args = {k: v for k, v in (arguments or {}).items() if k in PARAMS[name] and v is not False and v not in ("", [])}
    for key in ("wkt", "search-location"):
        if key in args:
            pairs = _COORD.findall(str(args[key]))
            if not pairs or any(abs(float(x) - lon) > NEAR_DEG or abs(float(y) - lat) > NEAR_DEG for x, y in pairs):
                raise AssistantError("Geometry must stay within about 2 km of the selected place")
    if "wkt" not in args and name not in ("oriented_imagery_query",):
        args["wkt"] = f"POINT({lon} {lat})"
    for key, cap in (("total-records", 10), ("page-size", 10), ("buffer-meter", 500)):
        if key in args:
            try:
                args[key] = min(float(args[key]), cap) if key == "buffer-meter" else min(int(args[key]), cap)
            except (TypeError, ValueError):
                args[key] = cap
    if name in ("embedding_extract", "property_metadata_extract", "structure_metadata_extract",
                "oriented_imagery_query"):
        args.setdefault("total-records", 5)
    if name == "elements_detect":
        args["buffer-meter"] = min(float(args.get("buffer-meter", 100) or 100), 150)
    return args


SYSTEM = ("You are Typecast's location assistant for film and site scouts. Answer questions about one selected "
          "place using Vexcel tools (aerial imagery metadata, obliques, elevation, property and structure "
          "metadata, semantic search, object detection). The selected place is POINT({lon} {lat}) in {city}; "
          "use WKT with longitude first and stay within 500 m unless asked. Prefer one or two precise tool calls, "
          "and set a boolean filter only when the question asks for that feature. "
          "Report numbers with units and say which tool they came from. Vexcel data are estimates from imagery: "
          "never claim access, permission, ownership, zoning or current availability. If a tool returns nothing, "
          "say so plainly. Keep the answer under 120 words.")


def ask(question: str, place: dict, city: str, *, mcp: VexcelMCP | None = None) -> dict:
    question = " ".join(str(question).split())[:500]
    if not question:
        raise ValueError("Ask a question about this place.")
    lat, lon = float(place["lat"]), float(place["lon"])
    from openai import OpenAI
    mcp = mcp or VexcelMCP()
    tools = mcp.connect()
    functions = []
    for t in tools:
        schema = t.get("inputSchema") or {}
        props = {k: v for k, v in (schema.get("properties") or {}).items() if k in PARAMS[t["name"]]}
        functions.append({"type": "function", "name": t["name"], "description": (t.get("description") or "")[:900],
                          "parameters": {"type": "object", "properties": props}})
    context = {k: place.get(k) for k in ("terrain", "match") if place.get(k)}
    items: list = [{"role": "user", "content": f"Known so far: {json.dumps(context)}\nQuestion: {question}"}]
    calls = []
    model = os.getenv("TYPECAST_LLM_MODEL", "").strip()
    key = os.getenv("LLM_API_KEY", "").strip()
    if not model or not key:
        raise AssistantError("The language model is not configured")
    with OpenAI(api_key=key, timeout=90, max_retries=0) as client:
        for _ in range(MAX_CALLS + 1):
            response = client.responses.create(model=model, instructions=SYSTEM.format(lat=lat, lon=lon, city=city),
                                               input=items, tools=functions, store=False)
            pending = [o for o in response.output if getattr(o, "type", "") == "function_call"]
            if not pending or len(calls) >= MAX_CALLS:
                return {"answer": (response.output_text or "").strip() or "No answer.", "calls": calls}
            items.extend(o.model_dump(exclude_none=True) for o in response.output)
            for call in pending:
                try:
                    arguments = guard(call.name, json.loads(call.arguments or "{}"), lat, lon)
                    output = mcp.call(call.name, arguments)
                    calls.append({"tool": call.name, "arguments": arguments, "ok": True})
                except (AssistantError, ValueError) as error:
                    output = f"Not run: {error}"
                    calls.append({"tool": call.name, "ok": False, "reason": str(error)})
                items.append({"type": "function_call_output", "call_id": call.call_id, "output": output})
    return {"answer": "Stopped after the tool-call limit.", "calls": calls}
