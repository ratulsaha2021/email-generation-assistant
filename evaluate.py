"""Evaluate generated emails using Ollama as an LLM-as-a-Judge."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd
import requests

from constants import OUTPUT_DIR, RESULTS_MODEL_A_PATH, SCENARIOS_PATH

OLLAMA_API = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.2:3b"

EVALUATOR_SYSTEM_PROMPT = """You are an expert email quality assessor. You will be given:
1. The email's intended purpose (intent)
2. Required key facts that must appear in the email
3. The requested tone
4. The generated email

Score the email on THREE metrics from 0.0 to 1.0:

1. fact_recall_score: What fraction of the key facts are accurately and naturally included in the email? Consider a fact "recalled" if its core meaning is clearly present, even if wording differs. Report as a decimal (e.g., 0.75 for 3 out of 4 facts).

2. tone_accuracy_score: How well does the email match the requested tone?
   - formal: proper salutation, professional language, complete sentences, appropriate sign-off
   - casual: warm, conversational, friendly tone
   - urgent: conveys time-sensitivity, uses direct language, clear call to action
   - empathetic: understanding, acknowledging difficulty, gracious language
   - assertive: confident, direct, action-oriented without aggression

3. clarity_professionalism_score: How clear, well-structured, and professionally written is the email? Consider: subject line quality, logical flow, grammar, sentence variety, appropriate length, and professional sign-off.

Return ONLY valid JSON in this exact format (no other text):
{"fact_recall_score": 0.0, "tone_accuracy_score": 0.0, "clarity_professionalism_score": 0.0}"""


def _call_ollama(messages: list[dict], temperature: float = 0.0) -> str:
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    for attempt in range(3):
        try:
            resp = requests.post(OLLAMA_API, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"].strip()
        except requests.exceptions.Timeout:
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                "Cannot connect to Ollama. Ensure it's running: ollama serve"
            )
    return ""


def _parse_json_from_response(text: str) -> dict[str, float] | None:
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def evaluate_single(
    scenario: dict[str, Any],
    generated_email: str,
) -> dict[str, float | int]:
    if not generated_email.strip():
        return {
            "scenario_id": scenario["scenario_id"],
            "fact_recall_score": 0.0,
            "tone_accuracy_score": 0.0,
            "clarity_professionalism_score": 0.0,
            "composite_score": 0.0,
        }

    facts_text = "\n".join(f"- {f}" for f in scenario.get("key_facts", []))
    user_content = (
        f"Intent: {scenario['intent']}\n\n"
        f"Required Key Facts:\n{facts_text}\n\n"
        f"Requested Tone: {scenario['tone']}\n\n"
        f"Generated Email:\n---\n{generated_email}\n---"
    )

    messages = [
        {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    response = _call_ollama(messages)
    scores = _parse_json_from_response(response)

    if scores is None:
        scores = {
            "fact_recall_score": 0.0,
            "tone_accuracy_score": 0.0,
            "clarity_professionalism_score": 0.0,
        }

    fact = float(scores.get("fact_recall_score", 0.0))
    tone = float(scores.get("tone_accuracy_score", 0.0))
    clarity = float(scores.get("clarity_professionalism_score", 0.0))

    return {
        "scenario_id": scenario["scenario_id"],
        "fact_recall_score": round(fact, 4),
        "tone_accuracy_score": round(tone, 4),
        "clarity_professionalism_score": round(clarity, 4),
        "composite_score": round(mean([fact, tone, clarity]), 4),
    }


def evaluate_all(
    scenarios: list[dict[str, Any]],
    generated_emails: list[dict[str, Any]],
    output_path: Path = RESULTS_MODEL_A_PATH,
) -> list[dict[str, Any]]:
    email_by_id = {item["scenario_id"]: item for item in generated_emails}
    results: list[dict[str, Any]] = []

    for scenario in scenarios:
        sid = scenario["scenario_id"]
        print(f"  Evaluating scenario {sid}/10...")
        generated = email_by_id.get(sid, {})
        email = generated.get("generated_email", "")
        scores = evaluate_single(scenario, email)
        results.append({
            "scenario_id": sid,
            "intent": scenario["intent"],
            "tone": scenario["tone"],
            **scores,
            "generated_email": email,
        })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(output_path, index=False)
    print_summary(results)
    return results


def print_summary(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No evaluation results available.")
        return
    averages = {
        "fact_recall_score": mean(r["fact_recall_score"] for r in results),
        "tone_accuracy_score": mean(r["tone_accuracy_score"] for r in results),
        "clarity_professionalism_score": mean(
            r["clarity_professionalism_score"] for r in results
        ),
        "composite_score": mean(r["composite_score"] for r in results),
    }
    print(f"  Avg fact_recall_score: {averages['fact_recall_score']:.4f}")
    print(f"  Avg tone_accuracy_score: {averages['tone_accuracy_score']:.4f}")
    print(f"  Avg clarity_professionalism_score: {averages['clarity_professionalism_score']:.4f}")
    print(f"  Avg composite_score: {averages['composite_score']:.4f}")


def _load_generated(path: str) -> list[dict[str, Any]]:
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        with Path(path).open("r", encoding="utf-8") as f:
            return json.load(f)
    frame = pd.read_csv(path)
    rows = frame.to_dict(orient="records")
    for row in rows:
        if isinstance(row.get("key_facts"), str):
            try:
                import ast
                row["key_facts"] = ast.literal_eval(row["key_facts"])
            except (SyntaxError, ValueError):
                row["key_facts"] = []
    return rows


if __name__ == "__main__":
    with SCENARIOS_PATH.open("r", encoding="utf-8") as f:
        scenarios_data = json.load(f)
    generated_path = OUTPUT_DIR / "generated_model_a.json"
    generated_data = _load_generated(generated_path)
    evaluate_all(scenarios_data, generated_data)
