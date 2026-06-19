"""Evaluate generated emails with rule-based and LLM-as-a-judge metrics."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from statistics import mean
from typing import Any

import nltk
import pandas as pd
from anthropic import Anthropic
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from config import ANTHROPIC_API_KEY, MAX_TOKENS, MODEL_B, OUTPUT_DIR


PROJECT_NLTK_DATA = Path(__file__).resolve().parent / "nltk_data"
if PROJECT_NLTK_DATA.exists():
    nltk.data.path.append(str(PROJECT_NLTK_DATA))


def _ensure_nltk_data() -> None:
    for resource, lookup in (
        ("punkt", "tokenizers/punkt"),
        ("punkt_tab", "tokenizers/punkt_tab"),
        ("stopwords", "corpora/stopwords"),
    ):
        try:
            nltk.data.find(lookup)
        except LookupError:
            nltk.download(resource, quiet=True)


def _meaningful_keywords(text: str) -> list[str]:
    _ensure_nltk_data()
    stop_words = set(stopwords.words("english"))
    tokens = word_tokenize(text.lower())
    return [
        token
        for token in tokens
        if token.isalnum() and token not in stop_words and len(token) > 1
    ]


def fact_recall_score(scenario: dict[str, Any], generated_email: str) -> float:
    """Score how many required key facts appear in the generated email."""
    email_lower = generated_email.lower()
    facts = scenario.get("key_facts", [])
    if not facts:
        return 0.0

    found = 0
    for fact in facts:
        keywords = _meaningful_keywords(fact)
        if not keywords:
            continue
        overlap = sum(1 for keyword in keywords if keyword in email_lower)
        if overlap / len(keywords) >= 0.60:
            found += 1
    return found / len(facts)


def _score_from_markers(
    generated_email: str,
    markers: set[str],
    base_score: float = 0.6,
) -> float:
    email_lower = generated_email.lower()
    marker_hits = sum(1 for marker in markers if marker in email_lower)
    return min(1.0, base_score + marker_hits * 0.1)


def offline_tone_accuracy_score(generated_email: str, tone: str) -> float:
    """Approximate tone matching locally for no-API demo runs."""
    tone_markers = {
        "formal": {"dear", "sincerely", "regards", "stakeholders", "review"},
        "casual": {"hi", "happy", "thanks", "hello", "everyone"},
        "urgent": {"urgent", "today", "priority", "as soon as possible", "critical"},
        "empathetic": {"sorry", "understand", "appreciate", "thank", "flexibility"},
        "assertive": {"action required", "need", "please confirm", "deadline", "approval"},
    }
    return round(_score_from_markers(generated_email, tone_markers.get(tone, set())), 4)


def offline_fluency_professionalism_score(generated_email: str) -> float:
    """Approximate grammar, structure, and professional polish locally."""
    if not generated_email.strip():
        return 0.0

    score = 0.55
    lines = [line.strip() for line in generated_email.splitlines() if line.strip()]
    word_count = len(re.findall(r"\b\w+\b", generated_email))
    sentence_count = len(re.findall(r"[.!?]", generated_email))

    if generated_email.lower().startswith("subject:"):
        score += 0.1
    if len(lines) >= 5:
        score += 0.1
    if 80 <= word_count <= 250:
        score += 0.1
    if sentence_count >= 4:
        score += 0.1
    if any(signoff in generated_email.lower() for signoff in ("regards", "best", "sincerely", "thanks")):
        score += 0.05

    return round(min(score, 1.0), 4)


def _judge_score(
    anthropic_client: Anthropic,
    prompt: str,
    default: float = 0.5,
) -> float:
    try:
        response = anthropic_client.messages.create(
            model=MODEL_B,
            max_tokens=16,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(block, "text", "") for block in getattr(response, "content", [])
        ).strip()
        match = re.search(r"\b([1-5])\b", text)
        if not match:
            return default
        return int(match.group(1)) / 5
    except Exception as exc:
        print(f"LLM judge error: {exc}")
        return default


def tone_accuracy_score(
    generated_email: str,
    tone: str,
    anthropic_client: Anthropic,
) -> float:
    prompt = f"""You are an expert communication evaluator. Rate how well the following email matches the requested tone of '{tone}'.
Email: {generated_email}
Score from 1 to 5 where:
1 = completely wrong tone
3 = partially matches tone
5 = perfectly matches tone
Respond with ONLY a single integer between 1 and 5. No explanation."""
    return _judge_score(anthropic_client, prompt)


def fluency_professionalism_score(
    generated_email: str,
    anthropic_client: Anthropic,
) -> float:
    prompt = f"""You are a professional writing expert. Evaluate the following email for:
1. Grammar and spelling correctness
2. Sentence clarity and readability
3. Professional tone and appropriate business language
4. Logical flow and structure
Rate the overall fluency and professionalism from 1 to 5 where:
1 = very poor quality
3 = acceptable quality
5 = excellent professional quality
Respond with ONLY a single integer between 1 and 5. No explanation.

Email: {generated_email}"""
    return _judge_score(anthropic_client, prompt)


def evaluate_single(
    scenario: dict[str, Any],
    generated_email: str,
    anthropic_client: Anthropic | None,
    offline: bool = False,
) -> dict[str, float | int]:
    fact_score = fact_recall_score(scenario, generated_email)
    if offline:
        tone_score = offline_tone_accuracy_score(generated_email, scenario["tone"])
        fluency_score = offline_fluency_professionalism_score(generated_email)
    else:
        if anthropic_client is None:
            raise ValueError("anthropic_client is required unless offline=True.")
        tone_score = tone_accuracy_score(
            generated_email, scenario["tone"], anthropic_client
        )
        fluency_score = fluency_professionalism_score(generated_email, anthropic_client)
    composite_score = mean([fact_score, tone_score, fluency_score])

    return {
        "scenario_id": scenario["scenario_id"],
        "fact_recall_score": round(fact_score, 4),
        "tone_accuracy_score": round(tone_score, 4),
        "fluency_score": round(fluency_score, 4),
        "composite_score": round(composite_score, 4),
    }


def evaluate_all(
    scenarios: list[dict[str, Any]],
    generated_emails: list[dict[str, Any]],
    anthropic_client: Anthropic | None,
    output_path: str = f"{OUTPUT_DIR}results_model_a.csv",
    offline: bool = False,
) -> list[dict[str, Any]]:
    """Evaluate all generated emails and save a CSV."""
    email_by_id = {item["scenario_id"]: item for item in generated_emails}
    results: list[dict[str, Any]] = []

    for scenario in scenarios:
        generated = email_by_id.get(scenario["scenario_id"], {})
        email = generated.get("generated_email", "")
        scores = evaluate_single(scenario, email, anthropic_client, offline=offline)
        results.append(
            {
                "scenario_id": scenario["scenario_id"],
                "intent": scenario["intent"],
                "tone": scenario["tone"],
                **scores,
                "generated_email": email,
            }
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(output_path, index=False)
    print_summary(results)
    return results


def print_summary(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No evaluation results available.")
        return
    print(f"Average fact_recall_score: {mean(row['fact_recall_score'] for row in results):.4f}")
    print(f"Average tone_accuracy_score: {mean(row['tone_accuracy_score'] for row in results):.4f}")
    print(f"Average fluency_score: {mean(row['fluency_score'] for row in results):.4f}")
    print(f"Overall average composite_score: {mean(row['composite_score'] for row in results):.4f}")


def _get_client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or .env file."
        )
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _load_generated(path: str) -> list[dict[str, Any]]:
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        with Path(path).open("r", encoding="utf-8") as file:
            return json.load(file)

    frame = pd.read_csv(path)
    rows = frame.to_dict(orient="records")
    for row in rows:
        if isinstance(row.get("key_facts"), str):
            try:
                row["key_facts"] = ast.literal_eval(row["key_facts"])
            except (SyntaxError, ValueError):
                row["key_facts"] = []
    return rows


if __name__ == "__main__":
    with Path("scenarios.json").open("r", encoding="utf-8") as file:
        scenarios_data = json.load(file)
    generated_path = f"{OUTPUT_DIR}generated_model_a.json"
    generated_data = _load_generated(generated_path)
    evaluate_all(scenarios_data, generated_data, _get_client())
