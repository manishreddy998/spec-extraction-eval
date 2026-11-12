"""Thin wrapper around the Anthropic Messages API for schema-constrained extraction.

Every call returns the parsed record plus what it cost, so the eval can compare methods on
accuracy *and* spend. Model and effort are configurable through the environment.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from dataclasses import dataclass
from typing import Optional, Type, TypeVar

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

MODEL = os.getenv("SPECX_MODEL", "claude-opus-5-5")
EFFORT = os.getenv("SPECX_EFFORT", "low")  # extraction is closer to classification than reasoning

# USD per million tokens (input, output); used for cost reporting only
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-4-8": (5.00, 25.00),
}

SYSTEM = (
    "You extract structured data from safety data sheets (SDS). "
    "Use only what the document states; never guess. If a field is not stated, return null "
    "(or an empty list). The text came from a PDF, so expect broken lines, bilingual "
    "English/French passages and occasional character corruption; read through those. "
    "Report English values."
)

# Response cache: every successful call is stored under a hash of its full request, so re-running
# the eval (or running it in CI) replays recorded answers for free. SPECX_CACHE=replay fails on a
# miss instead of calling the API; SPECX_CACHE=off always calls the API.
CACHE_MODE = os.getenv("SPECX_CACHE", "readwrite")
CACHE_DIR = pathlib.Path(__file__).resolve().parents[2] / "cache" / "llm"

T = TypeVar("T", bound=BaseModel)
_client: Optional[anthropic.Anthropic] = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=4)
    return _client


@dataclass
class CallResult:
    record: Optional[BaseModel]
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_s: float
    model: str
    error: Optional[str] = None
    cached: bool = False


def _cache_key(model: str, schema: type[BaseModel], content: str) -> str:
    blob = json.dumps([model, EFFORT, SYSTEM, schema.model_json_schema(), content], sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


# models with a server-side refusal fallback; Haiku has none, so the parameter is left off there
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


def extract(document: str, schema: Type[T], instructions: str, model: str = MODEL) -> CallResult:
    """One schema-constrained extraction call. The response is validated against `schema`."""
    content = f"<document>\n{document}\n</document>\n\n{instructions}"
    key = _cache_key(model, schema, content)
    path = CACHE_DIR / f"{key}.json"
    if CACHE_MODE != "off" and path.exists():
        hit = json.loads(path.read_text())
        return CallResult(schema.model_validate(hit["output"]), hit["input_tokens"], hit["output_tokens"],
                          hit["cost_usd"], hit["latency_s"], hit["model"], cached=True)
    if CACHE_MODE == "replay":
        return CallResult(None, 0, 0, 0.0, 0.0, model, "cache_miss")

    start = time.perf_counter()
    extra = {}
    if model in FALLBACK_MODELS:
        # if a safety classifier declines, the API retries on a fallback model inside the same call
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    try:
        resp = client().beta.messages.parse(
            model=model,
            max_tokens=16000,
            **extra,
            output_config={"effort": EFFORT},
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": content,
            }],
            output_format=schema,
        )
    except anthropic.APIStatusError as exc:
        return CallResult(None, 0, 0, 0.0, time.perf_counter() - start, model, f"api_error {exc.status_code}")
    latency = time.perf_counter() - start
    usage = resp.usage
    price_in, price_out = PRICES.get(resp.model, PRICES[model])
    cost = usage.input_tokens * price_in / 1e6 + usage.output_tokens * price_out / 1e6
    if resp.stop_reason == "refusal":
        return CallResult(None, usage.input_tokens, usage.output_tokens, cost, latency, resp.model, "refusal")
    result = CallResult(resp.parsed_output, usage.input_tokens, usage.output_tokens, cost, latency, resp.model)
    if CACHE_MODE != "off" and resp.parsed_output is not None:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "model": resp.model, "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
            "cost_usd": cost, "latency_s": latency, "output": resp.parsed_output.model_dump(mode="json"),
        }, indent=1))
    return result
