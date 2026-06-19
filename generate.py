"""Generate business emails for the configured scenario set."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from config import (
    ANTHROPIC_API_KEY,
    MAX_TOKENS,
    MODEL_A,
    OUTPUT_DIR,
    TEMPERATURE_A,
)


SYSTEM_PROMPT = """You are a senior business communications specialist with 15 years of experience writing professional corporate emails.

ALWAYS follow a strict Chain-of-Thought reasoning process BEFORE writing the email, using these exact steps wrapped in <thinking> tags:

<thinking>
Step 1 — Tone Analysis: What does the requested tone mean in practice? What vocabulary, sentence length, and formality level does it require?
Step 2 — Fact Mapping: List each key fact and decide WHERE in the email it will be placed (opening, body paragraph 1, body paragraph 2, closing).
Step 3 — Structure Planning: Decide the email structure — subject line, greeting, opening hook, body, call to action, sign-off.
Step 4 — Draft the Email: Write the final email following the plan above.
</thinking>

The <thinking> block must appear BEFORE the final email in the output. The final email must be clearly separated, starting with "---EMAIL---". Seamlessly weave ALL key facts into the email naturally — never as a raw list."""

USER_PROMPT_TEMPLATE = """Intent: {intent}
Key Facts:
{key_facts}
Tone: {tone}

Instruction: Follow your Chain-of-Thought steps inside <thinking> tags, then write the final email after the ---EMAIL--- separator. Include a Subject line. Do not add commentary after the email."""


def _get_client() -> Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY is not set. Add it to your environment or .env file."
        )
    return Anthropic(api_key=ANTHROPIC_API_KEY)


def _format_key_facts(key_facts: list[str]) -> str:
    return "\n".join(f"- {fact}" for fact in key_facts)


def _extract_text(response: Any) -> str:
    chunks: list[str] = []
    for block in getattr(response, "content", []):
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip()


def extract_email(full_response: str) -> str:
    """Return the final email after the separator, falling back to full text."""
    separator = "---EMAIL---"
    if separator in full_response:
        return full_response.split(separator, 1)[1].strip()
    return full_response.strip()


def generate_email(scenario: dict[str, Any], model: str, temperature: float) -> str:
    """Generate one email for a scenario using the requested Anthropic model."""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        intent=scenario["intent"],
        key_facts=_format_key_facts(scenario["key_facts"]),
        tone=scenario["tone"],
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return extract_email(_extract_text(response))
    except Exception as exc:  # Anthropic exceptions vary by SDK version.
        print(
            f"Error generating scenario {scenario.get('scenario_id')} "
            f"with model {model}: {exc}"
        )
        return ""


def run_generation(
    scenarios: list[dict[str, Any]], model: str, temperature: float
) -> list[dict[str, Any]]:
    """Generate emails for all scenarios."""
    generated: list[dict[str, Any]] = []
    for scenario in scenarios:
        email = generate_email(scenario, model, temperature)
        generated.append(
            {
                "scenario_id": scenario["scenario_id"],
                "intent": scenario["intent"],
                "tone": scenario["tone"],
                "key_facts": scenario["key_facts"],
                "generated_email": email,
            }
        )
        time.sleep(1)
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
    results = run_generation(scenarios, MODEL_A, TEMPERATURE_A)
    save_generated_emails(results, f"{OUTPUT_DIR}generated_model_a.json")
    print(f"Generated {len(results)} emails with {MODEL_A}.")
