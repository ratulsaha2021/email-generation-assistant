"""Generate business emails with Ollama using two prompting strategies.

Model A: role-playing system prompt + few-shot demonstrations (advanced).
Model B: a one-line instruction with no role or examples (baseline).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from constants import (
    GENERATED_PATHS,
    GENERATION_TEMPERATURE,
    GENERATOR_MODEL,
    MODEL_A_KEY,
    MODEL_A_NAME,
    MODEL_B_KEY,
    MODEL_B_NAME,
    SCENARIOS_PATH,
)
from llm import chat, ensure_models_available

PROFILE_NAMES = {MODEL_A_KEY: MODEL_A_NAME, MODEL_B_KEY: MODEL_B_NAME}

# Demonstrations use intents that do NOT appear in scenarios.json, so the
# few-shot strategy cannot score well by copying a test answer.
FEW_SHOT_EXAMPLES = [
    {
        "intent": "Confirm a vendor onboarding schedule",
        "key_facts": [
            "Onboarding for Brightline Logistics starts on March 3",
            "Security review documents are due by February 24",
            "Priya Shah is the primary onboarding contact",
        ],
        "tone": "formal",
        "email": (
            "Subject: Confirmation of Brightline Logistics Onboarding Schedule\n\n"
            "Dear Mr. Alvarez,\n\n"
            "Thank you for confirming Brightline Logistics as our new transportation partner. "
            "I am writing to confirm that onboarding will begin on March 3.\n\n"
            "To keep that date on track, we kindly ask that your team submit the security review "
            "documents by February 24. Our compliance group needs this time to complete its "
            "assessment before system access is granted.\n\n"
            "Priya Shah will serve as your primary onboarding contact and will coordinate "
            "training sessions, account setup, and any questions that arise along the way.\n\n"
            "Please reply to confirm receipt, and do not hesitate to reach out if any part of "
            "the schedule needs adjustment.\n\n"
            "Sincerely,\nMorgan Ellis\nVendor Management"
        ),
    },
    {
        "intent": "Announce a mandatory security patch",
        "key_facts": [
            "A critical VPN vulnerability was disclosed this morning",
            "All laptops must install the patch by 5 PM today",
            "Unpatched devices will lose network access tonight",
        ],
        "tone": "urgent",
        "email": (
            "Subject: ACTION REQUIRED by 5 PM Today: Install VPN Security Patch\n\n"
            "Hi everyone,\n\n"
            "A critical VPN vulnerability was disclosed this morning, and we need every laptop "
            "patched immediately.\n\n"
            "Please install the update from the Software Center by 5 PM today. It takes about "
            "ten minutes and requires one restart. Unpatched devices will lose network access "
            "tonight to protect the company network.\n\n"
            "If the installation fails or you cannot restart before the deadline, contact the "
            "IT help desk right away so we can assist.\n\n"
            "Thank you for acting quickly.\n\n"
            "Best regards,\nSam Okafor\nIT Security"
        ),
    },
    {
        "intent": "Invite the team to a celebration lunch",
        "key_facts": [
            "The team shipped the mobile app release last week",
            "Lunch is on Thursday at 12:30 at Rosa's Kitchen",
            "Please reply by Tuesday with dietary preferences",
        ],
        "tone": "casual",
        "email": (
            "Subject: Lunch on Us This Thursday!\n\n"
            "Hey team,\n\n"
            "We shipped the mobile app release last week, and that deserves a proper "
            "celebration! Let's grab lunch together on Thursday at 12:30 at Rosa's Kitchen.\n\n"
            "It's a relaxed get-together, so come hungry and ready to swap launch stories.\n\n"
            "Just reply by Tuesday with any dietary preferences so we can sort out the order.\n\n"
            "See you there!\n\nCheers,\nTaylor"
        ),
    },
]

FEW_SHOT_SYSTEM_PROMPT = """You are a senior business communications specialist. You write clear, professional emails that precisely match the requested tone and naturally incorporate every required key fact.

Rules:
- Match the requested tone exactly (formal, casual, urgent, empathetic, or assertive).
- Include EVERY key fact, woven into prose rather than copied as bullet points.
- Start with a specific "Subject:" line.
- Use a greeting, a focused body, a clear call to action, and a sign-off with a name.
- Keep the body between 100 and 250 words.
- Never use placeholders such as [Name], [Date], or [Your Name]; invent plausible names if needed.
- Output only the email, with no commentary before or after it."""

SIMPLE_SYSTEM_PROMPT = "Write a professional email based on the given intent, key facts, and tone."


def _format_request(item: dict[str, Any]) -> str:
    facts = "\n".join(f"- {fact}" for fact in item["key_facts"])
    return f"Intent: {item['intent']}\nKey Facts:\n{facts}\nTone: {item['tone']}"


def build_messages(scenario: dict[str, Any], profile_key: str) -> list[dict[str, str]]:
    if profile_key == MODEL_A_KEY:
        messages = [{"role": "system", "content": FEW_SHOT_SYSTEM_PROMPT}]
        for example in FEW_SHOT_EXAMPLES:
            messages.append({"role": "user", "content": _format_request(example)})
            messages.append({"role": "assistant", "content": example["email"]})
        messages.append({"role": "user", "content": _format_request(scenario)})
        return messages
    if profile_key == MODEL_B_KEY:
        return [
            {"role": "system", "content": SIMPLE_SYSTEM_PROMPT},
            {"role": "user", "content": _format_request(scenario)},
        ]
    raise ValueError(f"Unknown profile: {profile_key}")


def clean_email(text: str) -> str:
    """Strip code fences and any chatter before the subject line."""
    text = re.sub(r"^```[a-z]*\s*|\s*```$", "", text.strip())
    match = re.search(r"^\**\s*Subject:", text, re.IGNORECASE | re.MULTILINE)
    if match:
        text = text[match.start():]
    return text.strip()


def generate_email(scenario: dict[str, Any], profile_key: str) -> str:
    raw = chat(GENERATOR_MODEL, build_messages(scenario, profile_key), GENERATION_TEMPERATURE)
    return clean_email(raw)


def run_generation(scenarios: list[dict[str, Any]], profile_key: str) -> list[dict[str, Any]]:
    results = []
    for index, scenario in enumerate(scenarios, start=1):
        print(f"  [{PROFILE_NAMES[profile_key]}] scenario {scenario['scenario_id']} ({index}/{len(scenarios)})")
        results.append({
            "scenario_id": scenario["scenario_id"],
            "intent": scenario["intent"],
            "tone": scenario["tone"],
            "key_facts": scenario["key_facts"],
            "generator_model": GENERATOR_MODEL,
            "generated_email": generate_email(scenario, profile_key),
        })
    return results


def load_scenarios(path: Path = SCENARIOS_PATH, limit: int | None = None) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        scenarios = json.load(f)
    return scenarios[:limit] if limit else scenarios


def save_generated(items: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def load_generated(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=[MODEL_A_KEY, MODEL_B_KEY, "all"], default="all")
    parser.add_argument("--limit", type=int, help="Only use the first N scenarios")
    args = parser.parse_args()

    ensure_models_available(GENERATOR_MODEL)
    scenarios = load_scenarios(limit=args.limit)
    profiles = [MODEL_A_KEY, MODEL_B_KEY] if args.profile == "all" else [args.profile]
    for profile_key in profiles:
        items = run_generation(scenarios, profile_key)
        save_generated(items, GENERATED_PATHS[profile_key])
        print(f"Saved {len(items)} emails to {GENERATED_PATHS[profile_key]}")


if __name__ == "__main__":
    main()
