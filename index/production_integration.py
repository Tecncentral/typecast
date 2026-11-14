"""Shared-app routes and an in-process entrypoint for the production planner.

The HTTP route and Deep Agents tool deliberately use the same validated request
and planner; retrieval bounds, join gates and uncertainty remain authoritative.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from index import production


def run_production_plan(request: production.PlanRequest | dict[str, Any]) -> dict[str, Any]:
    """Run the bounded production planner without a nested HTTP request."""
    request = production.PlanRequest.model_validate(request)
    return production.post_production_plan(request)


def shared_router() -> APIRouter:
    """Expose explicit Director assets and indexed media, never a cache mount."""
    # Reuse the standalone preview's checked image and camera-plan handlers.
    # Copy only these routes: its home/search/evaluation app is not mounted here.
    from index.preview import app as preview_app

    router = APIRouter()
    router.include_router(production.router)
    allowed = {"/image/{shot_id}", "/api/plan/{shot_id}", "/api/viewer-config"}
    for route in preview_app.routes:
        if getattr(route, "path", None) in allowed:
            router.routes.append(route)
    return router
