"""Pure text parsing and command-recognition helpers."""

import json
import re
from typing import Any, Dict, Optional


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def has_bangla(text: str) -> bool:
    return any("\u0980" <= char <= "\u09ff" for char in text)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return clean_text(value).lower() in {"true", "yes", "y", "1", "needed"}


def parse_score(value: Any) -> int:
    if isinstance(value, (int, float)):
        score = int(value)
    else:
        match = re.search(r"\d+", clean_text(value))
        score = int(match.group()) if match else 0
    return max(0, min(10, score))


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract one JSON object from a plain or fenced model response."""

    normalized = clean_text(text)
    if not normalized:
        return None

    normalized = re.sub(r"```(?:json)?", "", normalized, flags=re.IGNORECASE).strip()
    candidates = [normalized]
    start = normalized.find("{")
    end = normalized.rfind("}")
    if start >= 0 and end > start:
        candidates.append(normalized[start : end + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def normalize_command_text(text: str) -> str:
    normalized = clean_text(text).lower()
    normalized = re.sub(r"[^a-zA-Z0-9\u0980-\u09FF\s']", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _matches_phrase(text: str, phrase: str) -> bool:
    """Match a command phrase without treating `yesterday` as `yes`."""

    if re.fullmatch(r"[a-z0-9 ']+", phrase):
        return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None
    return phrase in text


def is_start_command(text: str) -> bool:
    normalized = normalize_command_text(text)
    start_phrases = (
        "yes",
        "ok",
        "okay",
        "start",
        "ready",
        "i am ready",
        "i'm ready",
        "begin",
        "go",
        "হ্যাঁ",
        "হ্যা",
        "আচ্ছা",
        "শুরু",
        "শুরু করুন",
        "আমি প্রস্তুত",
    )
    return any(_matches_phrase(normalized, phrase) for phrase in start_phrases)


def is_skip_command(text: str) -> bool:
    normalized = normalize_command_text(text)
    skip_phrases = (
        "skip",
        "next",
        "next question",
        "next question please",
        "i don't know",
        "i dont know",
        "i can't answer",
        "i cant answer",
        "i cannot answer",
        "no idea",
        "pass",
        "বাদ",
        "পরের প্রশ্ন",
        "জানি না",
        "আমি জানি না",
        "উত্তর দিতে পারবো না",
        "স্কিপ",
    )
    return any(_matches_phrase(normalized, phrase) for phrase in skip_phrases)
