"""Treat model responses as untrusted text; never execute a tool name or code block."""

from __future__ import annotations

import json
import re

from nutritensor.domain.models import Candidate


class InvalidModelOutput(ValueError):
    pass


def decode_final(tokenizer, token_ids, thinking: bool) -> str:
    """Keep delimiters until the private reasoning segment has been discarded."""
    text = tokenizer.decode(token_ids, skip_special_tokens=False)
    # Qwen templates may already end with an opening think marker in the prompt.
    # Exhausting the generation budget before the close marker yields no answer.
    if thinking and "</think>" not in text:
        return ""
    answer = final_text(text)
    for token in getattr(tokenizer, "all_special_tokens", ()):
        if token:
            answer = answer.replace(token, "")
    return answer.strip()


def final_text(text: str) -> str:
    """Return final-answer text only, including when a thinking budget was exhausted."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1]
    elif "<think>" in text:
        return ""
    text = re.sub(r"<\|[^>]*\|>", "", text)
    return text.strip()


def extract_object(text: str) -> dict:
    cleaned = final_text(text)
    if len(cleaned) > 50000:
        raise InvalidModelOutput("Model response exceeds its structured-output limit")
    decoder = json.JSONDecoder()
    for index, character in enumerate(cleaned):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise InvalidModelOutput("Model did not return a JSON object")


def parse_candidates(text: str) -> list[Candidate]:
    payload = extract_object(text)
    foods = payload.get("foods")
    if not isinstance(foods, list) or len(foods) > 20:
        raise InvalidModelOutput("Expected at most twenty food candidates")
    candidates = []
    for item in foods:
        if not isinstance(item, dict):
            continue
        try:
            candidates.append(Candidate(
                label=str(item.get("label", "")).strip()[:160],
                confidence=item.get("confidence", 0.75) if item.get("confidence") is not None else 0.75,
                grams=item.get("grams"),
                evidence=str(item.get("evidence", ""))[:300],
            ))
        except ValueError:
            continue
    if not candidates:
        raise InvalidModelOutput("No valid food candidates were returned")
    return candidates


def safe_explanation(text: str, limit: int = 4000) -> str:
    answer = final_text(text)
    answer = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", answer)
    return answer[:limit]


def parse_food_observation(text: str) -> list[Candidate]:
    """Only accept explicit food observations, never text instructions or weights."""
    payload = extract_object(text)
    if payload.get("contains_food") is not True:
        raise InvalidModelOutput("No explicit food observation")
    candidates = parse_candidates(text)
    accepted = [candidate for candidate in candidates if candidate.confidence >= 0.75]
    if not accepted:
        raise InvalidModelOutput("No confident food observation")
    for candidate in accepted:
        candidate.grams = None
    return accepted
