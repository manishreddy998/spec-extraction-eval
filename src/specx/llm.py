"""Thin wrapper around the Anthropic Messages API for schema-constrained extraction.

Every call returns the parsed record plus what it cost, so the eval can compare methods on
accuracy *and* spend. Model and effort are configurable through the environment.
"""
from __future__ import annotations

import os
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


def extract(document: str, schema: Type[T], instructions: str) -> CallResult:
    """One schema-constrained extraction call. The response is validated against `schema`."""
    start = time.perf_counter()
    try:
        resp = client().beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if a safety classifier declines, retry on a fallback model
            output_config={"effort": EFFORT},
            system=SYSTEM,
            messages=[{
                "role": "user",
                "content": f"<document>\n{document}\n</document>\n\n{instructions}",
            }],
            output_format=schema,
        )
    except anthropic.APIStatusError as exc:
        return CallResult(None, 0, 0, 0.0, time.perf_counter() - start, MODEL, f"api_error {exc.status_code}")
    latency = time.perf_counter() - start
    usage = resp.usage
    price_in, price_out = PRICES.get(resp.model, PRICES[MODEL])
    cost = usage.input_tokens * price_in / 1e6 + usage.output_tokens * price_out / 1e6
    if resp.stop_reason == "refusal":
        return CallResult(None, usage.input_tokens, usage.output_tokens, cost, latency, resp.model, "refusal")
    return CallResult(resp.parsed_output, usage.input_tokens, usage.output_tokens, cost, latency, resp.model)
