"""Execution interface; replaced by the runtime implementation next."""
from agent import pipeline
from agent.interfaces import RunContext


def run_scout(ctx: RunContext, scene=None, example_shot_id=None):
    return pipeline.scout(ctx, scene or {"example_shot_id": example_shot_id})


def run_refine(ctx: RunContext, message):
    return pipeline.refine(ctx, pipeline._threads[ctx.thread_id], message)
