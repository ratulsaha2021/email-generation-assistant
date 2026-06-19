"""Run generation, evaluation, and side-by-side model comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from evaluate import evaluate_all
from generate import MODEL_A_NAME, MODEL_B_NAME, OUTPUT_DIR, run_generation


def load_scenarios(path: str = "scenarios.json") -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def summarize_csv(path: str, model_name: str) -> dict[str, float | str]:
    frame = pd.read_csv(path)
    return {
        "model_name": model_name,
        "avg_fact_recall": round(float(frame["fact_recall_score"].mean()), 4),
        "avg_tone_accuracy": round(float(frame["tone_accuracy_score"].mean()), 4),
        "avg_fluency": round(float(frame["fluency_score"].mean()), 4),
        "avg_composite": round(float(frame["composite_score"].mean()), 4),
    }


def save_summary(summary: dict[str, Any], path: str) -> None:
    with Path(path).open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)


def print_comparison_table(summary: dict[str, Any]) -> None:
    rows = [
        {
            "metric": "Fact Recall",
            "model_a": summary["model_a"]["avg_fact_recall"],
            "model_b": summary["model_b"]["avg_fact_recall"],
        },
        {
            "metric": "Tone Accuracy",
            "model_a": summary["model_a"]["avg_tone_accuracy"],
            "model_b": summary["model_b"]["avg_tone_accuracy"],
        },
        {
            "metric": "Fluency",
            "model_a": summary["model_a"]["avg_fluency"],
            "model_b": summary["model_b"]["avg_fluency"],
        },
        {
            "metric": "Composite",
            "model_a": summary["model_a"]["avg_composite"],
            "model_b": summary["model_b"]["avg_composite"],
        },
    ]
    print("\nModel Comparison")
    print(pd.DataFrame(rows).to_string(index=False))
    print(f"\nWinner: {summary['winner']}")


def run_pipeline() -> dict[str, Any]:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    scenarios = load_scenarios()

    print("Running pipeline in fully offline mode...")
    print(f"Generating emails with {MODEL_A_NAME}...")
    model_a_generated = run_generation(
        scenarios,
        model_profile="model_a",
    )
    print(f"Generating emails with {MODEL_B_NAME}...")
    model_b_generated = run_generation(
        scenarios,
        model_profile="model_b",
    )

    model_a_path = f"{OUTPUT_DIR}results_model_a.csv"
    model_b_path = f"{OUTPUT_DIR}results_model_b.csv"

    print(f"Evaluating {MODEL_A_NAME}...")
    evaluate_all(scenarios, model_a_generated, model_a_path)
    print(f"Evaluating {MODEL_B_NAME}...")
    evaluate_all(scenarios, model_b_generated, model_b_path)

    model_a_summary = summarize_csv(model_a_path, MODEL_A_NAME)
    model_b_summary = summarize_csv(model_b_path, MODEL_B_NAME)
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
    save_summary(summary, f"{OUTPUT_DIR}evaluation_summary.json")
    print_comparison_table(summary)
    return summary


if __name__ == "__main__":
    run_pipeline()
