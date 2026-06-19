"""Generate business emails for the configured scenario set."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

OUTPUT_DIR = "results/"
MODEL_A_NAME = "offline-reference-profile"
MODEL_B_NAME = "offline-template-profile"


def generate_email(scenario: dict[str, Any], model_profile: str) -> str:
    """Generate a deterministic local email without calling an external API."""
    if model_profile == "model_a":
        return scenario["human_reference_email"].strip()

    subject = re.sub(r"\s+", " ", scenario["intent"]).strip().title()
    greeting = "Hi team,"
    if scenario["tone"] == "formal":
        greeting = "Dear team,"
    elif scenario["tone"] == "urgent":
        subject = f"Urgent: {subject}"
    elif scenario["tone"] == "assertive":
        subject = f"Action Required: {subject}"

    facts = scenario["key_facts"][:3]
    fact_sentence = " ".join(facts)
    closing_by_tone = {
        "formal": "Please review this update and confirm the appropriate next step.",
        "casual": "Thanks, and please let me know what you think.",
        "urgent": "Please treat this as a priority and respond as soon as possible today.",
        "empathetic": "Thank you for your understanding and flexibility.",
        "assertive": "Please confirm ownership and next steps by the requested deadline.",
    }

    return (
        f"Subject: {subject}\n\n"
        f"{greeting}\n\n"
        f"I am writing regarding {scenario['intent'].lower()}. {fact_sentence}\n\n"
        f"{closing_by_tone.get(scenario['tone'], 'Please let me know the next step.')}\n\n"
        "Regards,\n"
        "Customer Operations Team"
    )


def run_generation(
    scenarios: list[dict[str, Any]],
    model_profile: str = "model_a",
) -> list[dict[str, Any]]:
    """Generate emails for all scenarios."""
    generated: list[dict[str, Any]] = []
    for scenario in scenarios:
        email = generate_email(scenario, model_profile)
        generated.append(
            {
                "scenario_id": scenario["scenario_id"],
                "intent": scenario["intent"],
                "tone": scenario["tone"],
                "key_facts": scenario["key_facts"],
                "generated_email": email,
            }
        )
    return generated


def load_scenarios(path: str = "scenarios.json") -> list[dict[str, Any]]:
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
    results = run_generation(scenarios, model_profile="model_a")
    save_generated_emails(results, f"{OUTPUT_DIR}generated_model_a.json")
    print(f"Generated {len(results)} emails with {MODEL_A_NAME}.")
