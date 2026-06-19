"""Generate business emails using Ollama with advanced prompting techniques."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from constants import (
    MODEL_A_KEY,
    MODEL_B_KEY,
    MODEL_A_NAME,
    MODEL_B_NAME,
    OUTPUT_DIR,
    SCENARIOS_PATH,
)

OLLAMA_API = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3.2:3b"

FEW_SHOT_EXAMPLES = [
    {
        "intent": "Follow up after a client meeting",
        "key_facts": [
            "The meeting was held on Tuesday with Acme Retail's operations team",
            "The client is interested in automating weekly inventory reports",
            "A pilot proposal will be sent by Friday",
        ],
        "tone": "formal",
        "email": "Subject: Follow-Up on Tuesday's Inventory Automation Discussion\n\nDear Ms. Carter,\n\nThank you for meeting with us on Tuesday and for including Acme Retail's operations team in such a productive discussion. I appreciated the opportunity to learn more about the team's current reporting process and the time spent each week preparing inventory updates across your regional locations.\n\nBased on the conversation, it is clear that automating weekly inventory reports could reduce manual effort, improve consistency, and give your managers faster visibility into stock exceptions. Our team is preparing a pilot proposal that will outline the recommended workflow, implementation timeline, success criteria, and estimated support requirements. I will send that proposal by Friday for your review.\n\nAs a next step, I recommend scheduling a technical discovery call next week with your reporting lead and our solutions architect. That session will help us confirm data sources, access requirements, and any integration considerations before the pilot begins.\n\nPlease let me know which times work best for your team next week.\n\nSincerely,\nJordan Lee",
    },
    {
        "intent": "Apologize for a service disruption",
        "key_facts": [
            "The dashboard service was unavailable for 42 minutes this morning",
            "The outage was caused by a failed database failover",
            "All services are now restored",
        ],
        "tone": "empathetic",
        "email": "Subject: Apology and Update on This Morning's Dashboard Disruption\n\nDear Customer,\n\nI am sorry for the dashboard service disruption you experienced this morning. The service was unavailable for 42 minutes, and we understand that even a short interruption can create real frustration when your team depends on the dashboard for daily decisions.\n\nOur initial investigation shows that the outage was caused by a failed database failover. The incident response team worked to stabilize the environment, restore access, and verify that dashboard functionality was operating normally before closing the active incident. All services are now restored.\n\nWe know that an apology is only part of the response. Our engineering team is completing a full root cause analysis, including why the failover did not complete as expected and what safeguards are needed to reduce the risk of recurrence. We will share that analysis within 48 hours.\n\nThank you for your patience while we worked through the issue. We take the reliability of our service seriously and appreciate the trust you place in us.\n\nSincerely,\nThe Customer Operations Team",
    },
]

FEW_SHOT_SYSTEM_PROMPT = """You are a senior business communications specialist. Your role is to write clear, professional emails that precisely match the requested tone and seamlessly incorporate all required key facts.

Follow these guidelines:
- Use the exact tone requested (formal, casual, urgent, empathetic, or assertive)
- Naturally include ALL key facts without listing them as bullet points
- Write a clear, relevant subject line
- Use proper business email structure: greeting, body, call to action, sign-off
- Keep the email between 100-250 words
- Do NOT include any explanatory text before or after the email"""

SIMPLE_SYSTEM_PROMPT = """Write a professional email based on the given intent, key facts, and tone. Include all key facts."""


def _call_ollama(messages: list[dict], temperature: float = 0.7) -> str:
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


def _build_few_shot_messages(scenario: dict[str, Any]) -> list[dict]:
    messages = [{"role": "system", "content": FEW_SHOT_SYSTEM_PROMPT}]

    for example in FEW_SHOT_EXAMPLES:
        user_content = (
            f"Intent: {example['intent']}\n"
            f"Key Facts:\n" + "\n".join(f"- {f}" for f in example["key_facts"]) + "\n"
            f"Tone: {example['tone']}"
        )
        messages.append({"role": "user", "content": user_content})
        messages.append({"role": "assistant", "content": example["email"]})

    user_content = (
        f"Intent: {scenario['intent']}\n"
        f"Key Facts:\n" + "\n".join(f"- {f}" for f in scenario["key_facts"]) + "\n"
        f"Tone: {scenario['tone']}"
    )
    messages.append({"role": "user", "content": user_content})
    return messages


def _build_simple_messages(scenario: dict[str, Any]) -> list[dict]:
    user_content = (
        f"Write a {scenario['tone']} email with this intent: {scenario['intent']}\n\n"
        f"Key facts to include:\n" + "\n".join(f"- {f}" for f in scenario["key_facts"])
    )
    return [
        {"role": "system", "content": SIMPLE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def generate_email(scenario: dict[str, Any], profile_key: str) -> str:
    if profile_key == MODEL_A_KEY:
        messages = _build_few_shot_messages(scenario)
    elif profile_key == MODEL_B_KEY:
        messages = _build_simple_messages(scenario)
    else:
        raise ValueError(f"Unknown profile: {profile_key}")

    return _call_ollama(messages)


def run_generation(
    scenarios: list[dict[str, Any]],
    profile_key: str = MODEL_A_KEY,
) -> list[dict[str, Any]]:
    results = []
    for scenario in scenarios:
        print(f"  Generating email {scenario['scenario_id']}/10...")
        email = generate_email(scenario, profile_key)
        results.append({
            "scenario_id": scenario["scenario_id"],
            "intent": scenario["intent"],
            "tone": scenario["tone"],
            "key_facts": scenario["key_facts"],
            "generated_email": email,
        })
    return results


def load_scenarios(path: Path = SCENARIOS_PATH) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def save_generated_emails(
    generated_emails: list[dict[str, Any]], path: str
) -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(generated_emails, f, indent=2)


if __name__ == "__main__":
    scenarios = load_scenarios()
    results = run_generation(scenarios, profile_key=MODEL_A_KEY)
    save_generated_emails(results, str(OUTPUT_DIR / "generated_model_a.json"))
    print(f"Generated {len(results)} emails with {MODEL_A_NAME}.")
