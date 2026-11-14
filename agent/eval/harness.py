"""Isolated, credential-free app access for mock evaluations and integration tests."""
from contextlib import ExitStack, contextmanager
import importlib
import os
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from unittest.mock import patch


OFFLINE_ENV = {
    "TYPECAST_USE_MOCKS": "1",
    "TYPECAST_ENGINE": "fixed",
    "TYPECAST_ENABLE_MODEL_PARSE": "0",
    "TYPECAST_ENABLE_VISION_RERANK": "0",
    "TYPECAST_ALLOW_VISION_UPLOAD": "0",
    "LANGSMITH_TRACING": "false",
    "LANGCHAIN_TRACING_V2": "false",
    **{key: "" for key in (
        "LLM_API_KEY", "VISION_API_KEY", "FALLBACK_API_KEY", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
        "LANGSMITH_API_KEY", "LANGCHAIN_API_KEY",
    )},
}


@contextmanager
def mock_app():
    """Never read .env credentials or connect a socket, even in a provisioned checkout."""
    attempts = []

    def no_network(*args, **kwargs):
        attempts.append("network")
        raise AssertionError("Network access is disabled for mock verification")

    def no_model(*args, **kwargs):
        attempts.append("model")
        raise AssertionError("Model calls are disabled for mock verification")

    with ExitStack() as stack:
        # Set these before importing app, whose dotenv loader preserves shell values.
        stack.enter_context(patch.dict(os.environ, OFFLINE_ENV))
        stack.enter_context(patch.object(socket.socket, "connect", no_network))
        stack.enter_context(patch.object(socket.socket, "connect_ex", no_network))
        from agent.app import app
        from agent import models, pipeline, state

        for module in ("data.costar_tools", "index.search", "data.vexcel_tools"):
            stack.enter_context(patch.object(importlib.import_module(module), "USE_MOCKS", True))
        stack.enter_context(patch.object(models.ModelProvider, "_call", no_model))
        directory = stack.enter_context(TemporaryDirectory(prefix="typecast-mock-"))
        stack.enter_context(patch.object(state, "CACHE_ROOT", Path(directory)))
        with state._lock:
            memory, expires = dict(state._memory), dict(state._expires)
        pipeline_threads = dict(pipeline._threads)
        try:
            yield app
            assert not attempts, f"Mock verification attempted {', '.join(attempts)} access"
        finally:
            with state._lock:
                state._memory.clear()
                state._memory.update(memory)
                state._expires.clear()
                state._expires.update(expires)
            pipeline._threads.clear()
            pipeline._threads.update(pipeline_threads)
