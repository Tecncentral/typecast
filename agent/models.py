"""Lazy environment-configured structured-output adapters; no sensitive logging."""
from __future__ import annotations
import os
import json
from threading import Event as ThreadEvent
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


class ModelRateLimitError(RuntimeError):
    status_code = 429


_RATE_LIMITED = ThreadEvent()


def rate_limit_seen() -> bool:
    return _RATE_LIMITED.is_set()


def reset_rate_limit() -> None:
    """Reset only when deliberately starting a new experiment/process session."""
    _RATE_LIMITED.clear()


def mark_rate_limit() -> None:
    _RATE_LIMITED.set()


def is_rate_limit_error(error: BaseException) -> bool:
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if (getattr(error, "status_code", None) == 429
                or getattr(getattr(error, "response", None), "status_code", None) == 429):
            return True
        error = error.__cause__ or error.__context__
    return False


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
                   image_url: str | None = None, image_urls: list[str] | None = None,
                   timeout: float = 20.0) -> T:
        if image_urls is not None:
            if (image_url is not None or not isinstance(image_urls, list) or not 1 <= len(image_urls) <= 10
                    or any(not isinstance(image, str) or not image for image in image_urls)):
                raise ValueError("Supply either one image_url or 1..10 image_urls")
        image_input = image_urls if image_urls is not None else image_url
        if rate_limit_seen():
            raise ModelRateLimitError("A rate limit already stopped this experiment")
        if not self.configured():
            raise ModelUnavailable("A provider key and model are required")
        if timeout <= 0:
            raise TimeoutError("Model request budget exhausted")
        fallback = bool(self.provider != "anthropic" and self._fallback_provider == "anthropic"
                        and self._fallback_key and self._fallback_model)
        deadline = monotonic() + timeout

        def validate_before_deadline(result):
            parsed = output_model.model_validate(result)
            if monotonic() > deadline:
                raise TimeoutError("Model response exceeded request deadline")
            return parsed

        def invoke(provider, model, key, budget):
            try:
                return self._call(provider, model, key, instructions, text,
                                  output_model, image_input, budget)
            except Exception as error:
                if is_rate_limit_error(error):
                    mark_rate_limit()
                    if self.emit:
                        self.emit(Event(type="rate_limit", agent="models",
                                        text="Model rate_limited=1; further requests stopped; no retry or fallback."))
                    raise ModelRateLimitError("Model rate limit reached; further requests stopped") from None
                raise

        try:
            primary_timeout = timeout * 0.7 if fallback else timeout
            return validate_before_deadline(invoke(self.provider, self.model, self._key, primary_timeout))
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise
            remaining = deadline - monotonic()
            if not fallback or remaining <= 0:
                raise
            if self.emit:
                role = "vision" if self.vision else "text"
                self.emit(Event(type="fallback", agent="models", text=(
                    f"Primary {role} model failed ({type(exc).__name__}); using the configured anthropic fallback."
                )))
            return validate_before_deadline(invoke("anthropic", self._fallback_model, self._fallback_key, remaining))

    def _call(self, provider: str, model: str, key: str, instructions: str,
              text: str, output_model: type[T], image_url: str | list[str] | None, timeout: float) -> T:
        images = image_url if isinstance(image_url, list) else ([image_url] if image_url else [])
        if rate_limit_seen():
            raise ModelRateLimitError("A rate limit already stopped this experiment")
        if self.emit:
            self.emit(Event(type="model_request", agent="models", text=json.dumps(
                {"provider_calls": 1, "images": len(images), "vision": self.vision}, sort_keys=True)))
        if provider == "openai":
            # Verified installed openai 3.51.0 Responses.parse parameters.
            from openai import OpenAI
            content = [{"type": "input_text", "text": text}]
            content.extend({"type": "input_image", "image_url": image, "detail": "auto"} for image in images)
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
            for image in images:
                if image.startswith("data:"):
                    header, data = image.split(",", 1)
                    source = {"type": "base64", "media_type": header[5:].split(";", 1)[0], "data": data}
                else:
                    source = {"type": "url", "url": image}
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
