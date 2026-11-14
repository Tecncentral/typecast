"""Lazy environment-configured structured-output adapters; no sensitive logging."""
from __future__ import annotations
import os
from time import monotonic
from typing import Callable, TypeVar
from pydantic import BaseModel
from contracts.schemas import Event

T = TypeVar("T", bound=BaseModel)


def enabled(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


class ModelUnavailable(RuntimeError):
    pass


class ModelProvider:
    """The optional Anthropic backup shares a bounded request timeout budget."""
    def __init__(self, *, vision: bool = False, emit: Callable[[Event], None] | None = None):
        self.vision, self.emit = vision, emit
        self.provider = os.getenv("TYPECAST_LLM_PROVIDER", "openai").strip().lower()
        self.model = os.getenv("TYPECAST_VISION_MODEL" if vision else "TYPECAST_LLM_MODEL", "").strip()
        self._key = os.getenv("VISION_API_KEY" if vision else "LLM_API_KEY", "").strip()
        self._fallback_provider = os.getenv("TYPECAST_FALLBACK_PROVIDER", "").strip().lower()
        self._fallback_model = os.getenv("TYPECAST_FALLBACK_MODEL", "").strip()
        self._fallback_key = os.getenv("FALLBACK_API_KEY", "").strip()
        self.reasoning_effort = os.getenv("TYPECAST_REASONING_EFFORT", "").strip()

    def configured(self) -> bool:
        return bool(self._key and self.model and self.provider in {"openai", "anthropic"})

    @property
    def cache_identity(self) -> str:
        return ":".join((self.provider, self.model, self.reasoning_effort,
                         self._fallback_provider, self._fallback_model))

    def structured(self, instructions: str, text: str, output_model: type[T], *,
                   image_url: str | None = None, timeout: float = 20.0) -> T:
        if not self.configured():
            raise ModelUnavailable("A provider key and model are required")
        if timeout <= 0:
            raise TimeoutError("Model request budget exhausted")
        fallback = bool(self.provider != "anthropic" and self._fallback_provider == "anthropic"
                        and self._fallback_key and self._fallback_model)
        deadline = monotonic() + timeout
        try:
            primary_timeout = timeout * 0.7 if fallback else timeout
            return output_model.model_validate(self._call(
                self.provider, self.model, self._key, instructions, text,
                output_model, image_url, primary_timeout))
        except Exception as exc:
            remaining = deadline - monotonic()
            if not fallback or remaining <= 0:
                raise
            if self.emit:
                role = "vision" if self.vision else "text"
                self.emit(Event(type="fallback", agent="models", text=(
                    f"Primary {role} model failed ({type(exc).__name__}); using the configured anthropic fallback."
                )))
            return output_model.model_validate(self._call(
                "anthropic", self._fallback_model, self._fallback_key,
                instructions, text, output_model, image_url, remaining))

    def _call(self, provider: str, model: str, key: str, instructions: str,
              text: str, output_model: type[T], image_url: str | None, timeout: float) -> T:
        if provider == "openai":
            # Verified installed openai 3.51.0 Responses.parse parameters.
            from openai import OpenAI
            content = [{"type": "input_text", "text": text}]
            if image_url:
                content.append({"type": "input_image", "image_url": image_url, "detail": "auto"})
            options = {"reasoning": {"effort": self.reasoning_effort}} if self.reasoning_effort else {}
            with OpenAI(api_key=key, timeout=timeout, max_retries=0) as client:
                response = client.responses.parse(
                    model=model, instructions=instructions,
                    input=[{"role": "user", "content": content}],
                    text_format=output_model, store=False, timeout=timeout, **options)
                result = response.output_parsed
        elif provider == "anthropic":
            # Verified installed anthropic 2.8.0 messages.parse + parsed_output.
            from anthropic import Anthropic
            content = [{"type": "text", "text": text}]
            if image_url:
                if image_url.startswith("data:"):
                    header, data = image_url.split(",", 1)
                    source = {"type": "base64", "media_type": header[5:].split(";", 1)[0], "data": data}
                else:
                    source = {"type": "url", "url": image_url}
                content.append({"type": "image", "source": source})
            with Anthropic(api_key=key, timeout=timeout, max_retries=0) as client:
                response = client.messages.parse(
                    model=model, system=instructions, messages=[{"role": "user", "content": content}],
                    output_format=output_model, max_tokens=4096, timeout=timeout)
                result = response.parsed_output
        else:
            raise ModelUnavailable("Unsupported model provider")
        if result is None:
            raise ValueError("Provider returned no validated structured output")
        return output_model.model_validate(result)


def get_provider(*, vision: bool = False, emit: Callable[[Event], None] | None = None) -> ModelProvider:
    return ModelProvider(vision=vision, emit=emit)


def configured(*, vision: bool = False) -> bool:
    return get_provider(vision=vision).configured()
