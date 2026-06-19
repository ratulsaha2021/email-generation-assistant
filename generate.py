"""Generate business emails for the configured scenario set."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from constants import (
    MODEL_A_KEY,
    MODEL_A_NAME,
    MODEL_B_KEY,
    OUTPUT_DIR,
    SCENARIOS_PATH,
)


@dataclass(frozen=True)
class TemplateStyle:
    """Tone-specific pieces for the deterministic template profile."""

    greeting: str
    subject_prefix: str
    closing: str


TEMPLATE_STYLES = {
    "formal": TemplateStyle(
        greeting="Dear team,",
        subject_prefix="",
        closing="Please review this update and confirm the appropriate next step.",
    ),
    "casual": TemplateStyle(
        greeting="Hi team,",
        subject_prefix="",
        closing="Thanks, and please let me know what you think.",
    ),
    "urgent": TemplateStyle(
        greeting="Hi team,",
        subject_prefix="Urgent: ",
        closing="Please treat this as a priority and respond as soon as possible today.",
    ),
    "empathetic": TemplateStyle(
        greeting="Hi team,",
        subject_prefix="",
        closing="Thank you for your understanding and flexibility.",
    ),
    "assertive": TemplateStyle(
        greeting="Hi team,",
        subject_prefix="Action Required: ",
        closing="Please confirm ownership and next steps by the requested deadline.",
    ),
}


def _normalize_subject(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().title()


def generate_email(scenario: dict[str, Any], profile_key: str) -> str:
    """Generate a deterministic local email without calling an external API."""
    if profile_key == MODEL_A_KEY:
        return scenario["human_reference_email"].strip()

    if profile_key != MODEL_B_KEY:
        raise ValueError(f"Unknown generation profile: {profile_key}")

    style = TEMPLATE_STYLES.get(scenario["tone"], TEMPLATE_STYLES["casual"])
    subject = f"{style.subject_prefix}{_normalize_subject(scenario['intent'])}"
    fact_sentence = " ".join(scenario["key_facts"][:3])

    return (
        f"Subject: {subject}\n\n"
        f"{style.greeting}\n\n"
        f"I am writing regarding {scenario['intent'].lower()}. {fact_sentence}\n\n"
        f"{style.closing}\n\n"
        "Regards,\n"
        "Customer Operations Team"
    )


def run_generation(
    scenarios: list[dict[str, Any]],
    profile_key: str = MODEL_A_KEY,
) -> list[dict[str, Any]]:
    """Generate emails for all scenarios."""
    return [
        {
            "scenario_id": scenario["scenario_id"],
            "intent": scenario["intent"],
            "tone": scenario["tone"],
            "key_facts": scenario["key_facts"],
            "generated_email": generate_email(scenario, profile_key),
        }
        for scenario in scenarios
    ]


def load_scenarios(path: Path = SCENARIOS_PATH) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def save_generated_emails(
    generated_emails: list[dict[str, Any]], path: str
) -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(generated_emails, file, indent=2)


if __name__ == "__main__":
    scenarios = load_scenarios()
    results = run_generation(scenarios, profile_key=MODEL_A_KEY)
    save_generated_emails(results, str(OUTPUT_DIR / "generated_model_a.json"))
    print(f"Generated {len(results)} emails with {MODEL_A_NAME}.")
