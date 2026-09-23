"""Score emails with an LLM-as-a-Judge plus deterministic sanity checks.

Metrics (all 0.0-1.0):
    fact_recall_score              judged present facts / total facts
    tone_accuracy_score            1-5 rubric score rescaled to 0-1
    clarity_professionalism_score  1-5 rubric score rescaled to 0-1
    composite_score                mean of the three

The judge assesses each key fact individually and gives its reasoning before
each score; recall is computed from those per-fact verdicts, not guessed.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd

from constants import (
    GENERATED_PATHS,
    JUDGE_MODEL,
    JUDGE_TEMPERATURE,
    MODEL_A_KEY,
    MODEL_B_KEY,
    REFERENCE_KEY,
    RESULTS_PATHS,
)
from generate import load_generated, load_scenarios
from llm import OllamaError, chat_json, ensure_models_available

METRICS = ["fact_recall_score", "tone_accuracy_score", "clarity_professionalism_score"]

JUDGE_SYSTEM_PROMPT = """You are a strict, impartial evaluator of business emails. You receive an email's intent, its required key facts, the requested tone, and the email itself.

1. For EACH key fact, in order, quote the sentence from the email that conveys it (or "none") and decide whether its core meaning is present. Specific details (names, dates, numbers, amounts) must be correct for the fact to count; paraphrasing is fine.

2. Tone accuracy (1-5) against the requested tone:
   - formal: courteous salutation, precise professional language, no slang, formal sign-off
   - casual: warm, conversational, friendly, relaxed phrasing
   - urgent: time-sensitivity is explicit early, direct language, clear immediate call to action
   - empathetic: acknowledges impact or feelings, gracious and considerate wording
   - assertive: confident, direct, firm requests and deadlines, without aggression
   5 = unmistakably the requested tone throughout; 3 = partly matches or mixed; 1 = wrong tone.

3. Clarity & professionalism (1-5): specific subject line, logical flow, grammar, concision (roughly 100-250 words), clear call to action, proper sign-off. Unfilled placeholders such as [Name] or [Date], meta-commentary, or multiple alternative drafts are serious defects (score 2 or lower).
   5 = ready to send unchanged; 3 = usable after edits; 1 = unusable.

Be critical: reserve 5 for genuinely excellent work."""


def judge_schema(num_facts: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "facts": {
                "type": "array",
                "minItems": num_facts,
                "maxItems": num_facts,
                "items": {
                    "type": "object",
                    "properties": {
                        "evidence": {"type": "string"},
                        "present": {"type": "boolean"},
                    },
                    "required": ["evidence", "present"],
                },
            },
            "tone_rationale": {"type": "string"},
            "tone_score": {"type": "integer", "minimum": 1, "maximum": 5},
            "clarity_rationale": {"type": "string"},
            "clarity_score": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        "required": ["facts", "tone_rationale", "tone_score", "clarity_rationale", "clarity_score"],
    }


PLACEHOLDER_RE = re.compile(r"\[[^\]\n]{2,40}\]")


def _rescale(score: int) -> float:
    return round((min(max(int(score), 1), 5) - 1) / 4, 4)


def evaluate_single(scenario: dict[str, Any], email: str) -> dict[str, Any]:
    facts = scenario["key_facts"]
    diagnostics = {
        "word_count": len(email.split()),
        "placeholder_count": len(PLACEHOLDER_RE.findall(email)),
        "has_subject": bool(re.search(r"^\**\s*Subject:", email, re.I | re.M)),
    }
    empty = {m: 0.0 for m in METRICS} | {"composite_score": 0.0, "missed_facts": "", "judge_notes": ""}
    if not email.strip():
        return empty | diagnostics | {"judge_notes": "empty email"}

    fact_lines = "\n".join(f"{i}. {fact}" for i, fact in enumerate(facts, start=1))
    user_content = (
        f"Intent: {scenario['intent']}\n\n"
        f"Required key facts:\n{fact_lines}\n\n"
        f"Requested tone: {scenario['tone']}\n\n"
        f"Email:\n<<<\n{email}\n>>>"
    )
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        verdict = chat_json(JUDGE_MODEL, messages, judge_schema(len(facts)), JUDGE_TEMPERATURE)
    except OllamaError as exc:
        print(f"    judge failed for scenario {scenario['scenario_id']}: {exc}")
        return empty | diagnostics | {"judge_notes": f"judge error: {exc}"}

    fact_verdicts = verdict["facts"][: len(facts)]
    present = [bool(v.get("present")) for v in fact_verdicts]
    present += [False] * (len(facts) - len(present))
    scores = {
        "fact_recall_score": round(sum(present) / len(facts), 4),
        "tone_accuracy_score": _rescale(verdict["tone_score"]),
        "clarity_professionalism_score": _rescale(verdict["clarity_score"]),
    }
    return scores | {
        "composite_score": round(mean(scores.values()), 4),
        "missed_facts": " | ".join(f for f, ok in zip(facts, present) if not ok),
        "judge_notes": f"Tone: {verdict['tone_rationale']} Clarity: {verdict['clarity_rationale']}",
    } | diagnostics


def evaluate_all(
    scenarios: list[dict[str, Any]],
    emails_by_id: dict[int, str],
    output_path: Path,
    label: str,
) -> pd.DataFrame:
    rows = []
    for index, scenario in enumerate(scenarios, start=1):
        sid = scenario["scenario_id"]
        print(f"  [{label}] judging scenario {sid} ({index}/{len(scenarios)})")
        email = emails_by_id.get(sid, "")
        rows.append({
            "scenario_id": sid,
            "intent": scenario["intent"],
            "tone": scenario["tone"],
            **evaluate_single(scenario, email),
            "generated_email": email,
        })

    frame = pd.DataFrame(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    averages = ", ".join(f"{m.removesuffix('_score')}={frame[m].mean():.3f}" for m in METRICS + ["composite_score"])
    print(f"  [{label}] {averages}")
    return frame


def with_reference(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scenarios that have a human reference email (it is optional)."""
    return [s for s in scenarios if str(s.get("human_reference_email") or "").strip()]


def emails_for(profile_key: str, scenarios: list[dict[str, Any]]) -> dict[int, str]:
    if profile_key == REFERENCE_KEY:
        return {s["scenario_id"]: s["human_reference_email"] for s in with_reference(scenarios)}
    generated = load_generated(GENERATED_PATHS[profile_key])
    return {item["scenario_id"]: item["generated_email"] for item in generated}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", choices=[MODEL_A_KEY, MODEL_B_KEY, REFERENCE_KEY, "all"], default="all")
    parser.add_argument("--limit", type=int, help="Only use the first N scenarios")
    args = parser.parse_args()

    ensure_models_available(JUDGE_MODEL)
    scenarios = load_scenarios(limit=args.limit)
    profiles = [MODEL_A_KEY, MODEL_B_KEY, REFERENCE_KEY] if args.profile == "all" else [args.profile]
    for profile_key in profiles:
        subset = with_reference(scenarios) if profile_key == REFERENCE_KEY else scenarios
        if not subset:
            print(f"  [{profile_key}] skipped: no scenario has a human reference email")
            continue
        evaluate_all(subset, emails_for(profile_key, scenarios), RESULTS_PATHS[profile_key], profile_key)


if __name__ == "__main__":
    main()
