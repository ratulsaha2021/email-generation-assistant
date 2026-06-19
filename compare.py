"""Run generation, evaluation, and side-by-side model comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from constants import (
    EVALUATION_SUMMARY_PATH,
    MODEL_A_KEY,
    MODEL_A_NAME,
    MODEL_B_KEY,
    MODEL_B_NAME,
    OUTPUT_DIR,
    RESULTS_MODEL_A_PATH,
    RESULTS_MODEL_B_PATH,
    SCENARIOS_PATH,
)
from evaluate import evaluate_all
from generate import run_generation


def load_scenarios(path: Path = SCENARIOS_PATH) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def summarize_csv(path: Path, model_name: str) -> dict[str, float | str]:
    frame = pd.read_csv(path)
    return {
        "model_name": model_name,
        "avg_fact_recall": round(float(frame["fact_recall_score"].mean()), 4),
        "avg_tone_accuracy": round(float(frame["tone_accuracy_score"].mean()), 4),
        "avg_fluency": round(float(frame["fluency_score"].mean()), 4),
        "avg_composite": round(float(frame["composite_score"].mean()), 4),
    }


def save_summary(summary: dict[str, Any], path: Path) -> None:
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)


def print_comparison_table(summary: dict[str, Any]) -> None:
    metric_labels = {
        "avg_fact_recall": "Fact Recall",
        "avg_tone_accuracy": "Tone Accuracy",
        "avg_fluency": "Fluency",
        "avg_composite": "Composite",
    }
    rows = [
        {
            "metric": label,
            "model_a": summary["model_a"][key],
            "model_b": summary["model_b"][key],
        }
        for key, label in metric_labels.items()
    ]
    print("\nModel Comparison")
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nWinner: {summary['winner']}")


def run_pipeline() -> dict[str, Any]:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios()

    print("Running pipeline in fully offline mode...")
    print(f"Generating emails with {MODEL_A_NAME}...")
    model_a_generated = run_generation(scenarios, profile_key=MODEL_A_KEY)
    print(f"Generating emails with {MODEL_B_NAME}...")
    model_b_generated = run_generation(scenarios, profile_key=MODEL_B_KEY)

    print(f"Evaluating {MODEL_A_NAME}...")
    evaluate_all(scenarios, model_a_generated, RESULTS_MODEL_A_PATH)
    print(f"Evaluating {MODEL_B_NAME}...")
    evaluate_all(scenarios, model_b_generated, RESULTS_MODEL_B_PATH)

    model_a_summary = summarize_csv(RESULTS_MODEL_A_PATH, MODEL_A_NAME)
    model_b_summary = summarize_csv(RESULTS_MODEL_B_PATH, MODEL_B_NAME)
    winner = (
        "model_a"
        if model_a_summary["avg_composite"] >= model_b_summary["avg_composite"]
        else "model_b"
    )

    summary = {
        "model_a": model_a_summary,
        "model_b": model_b_summary,
        "winner": winner,
    }
    save_summary(summary, EVALUATION_SUMMARY_PATH)
    print_comparison_table(summary)
    return summary


if __name__ == "__main__":
    run_pipeline()
