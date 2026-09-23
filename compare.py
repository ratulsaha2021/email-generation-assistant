"""Run the full pipeline: generate -> judge -> summarize -> write report.

Examples:
    python compare.py                    # full run on all 10 scenarios
    python compare.py --skip-generation  # re-judge existing generated emails
    python compare.py --limit 2          # quick smoke test
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import pandas as pd

from constants import (
    EVALUATION_SUMMARY_PATH,
    GENERATED_PATHS,
    GENERATOR_MODEL,
    JUDGE_MODEL,
    MODEL_A_KEY,
    MODEL_A_NAME,
    MODEL_B_KEY,
    MODEL_B_NAME,
    REFERENCE_KEY,
    REFERENCE_NAME,
    RESULTS_PATHS,
)
from evaluate import METRICS, emails_for, evaluate_all, with_reference
from generate import load_scenarios, run_generation, save_generated
from llm import OllamaError, ensure_models_available
from report import write_report

PROFILE_NAMES = {MODEL_A_KEY: MODEL_A_NAME, MODEL_B_KEY: MODEL_B_NAME, REFERENCE_KEY: REFERENCE_NAME}


def summarize(frame: pd.DataFrame, name: str) -> dict[str, Any]:
    return {
        "model_name": name,
        "scenarios": int(len(frame)),
        **{f"avg_{m.removesuffix('_score')}": round(float(frame[m].mean()), 4) for m in METRICS},
        "avg_composite": round(float(frame["composite_score"].mean()), 4),
        "total_placeholders": int(frame["placeholder_count"].sum()),
        "avg_word_count": round(float(frame["word_count"].mean()), 1),
    }


def print_comparison(summary: dict[str, Any]) -> None:
    keys = ["avg_fact_recall", "avg_tone_accuracy", "avg_clarity_professionalism", "avg_composite", "total_placeholders"]
    table = pd.DataFrame(
        {summary[k]["model_name"]: [summary[k][m] for m in keys] for k in (MODEL_A_KEY, MODEL_B_KEY, REFERENCE_KEY) if k in summary},
        index=keys,
    )
    print("\n=== Model Comparison ===")
    print(table.to_string())
    print(f"\nWinner: {summary['winner']} (composite margin {summary['composite_margin']:+.4f})")


def run_pipeline(skip_generation: bool = False, limit: int | None = None) -> dict[str, Any]:
    scenarios = load_scenarios(limit=limit)
    if not scenarios:
        raise SystemExit("scenarios.json has no scenarios. Add at least one before running the evaluation.")
    print(f"Generator: {GENERATOR_MODEL} | Judge: {JUDGE_MODEL} | Scenarios: {len(scenarios)}")

    if skip_generation:
        missing = [str(p) for p in GENERATED_PATHS.values() if not p.exists()]
        if missing:
            raise SystemExit(f"--skip-generation needs existing files: {', '.join(missing)}")
    else:
        ensure_models_available(GENERATOR_MODEL)
        print("\n--- Generation ---")
        for key in (MODEL_A_KEY, MODEL_B_KEY):
            save_generated(run_generation(scenarios, key), GENERATED_PATHS[key])

    # All judging happens after all generation so each model is loaded once.
    ensure_models_available(JUDGE_MODEL)
    print("\n--- Evaluation (LLM-as-a-Judge) ---")
    summary: dict[str, Any] = {"generator_model": GENERATOR_MODEL, "judge_model": JUDGE_MODEL}
    for key in (MODEL_A_KEY, MODEL_B_KEY, REFERENCE_KEY):
        # Reference emails are optional, so the baseline covers only scenarios that have one.
        subset = with_reference(scenarios) if key == REFERENCE_KEY else scenarios
        if not subset:
            RESULTS_PATHS[key].unlink(missing_ok=True)
            print(f"  [{PROFILE_NAMES[key]}] skipped: no scenario has a human reference email")
            continue
        frame = evaluate_all(subset, emails_for(key, scenarios), RESULTS_PATHS[key], PROFILE_NAMES[key])
        summary[key] = summarize(frame, PROFILE_NAMES[key])

    margin = summary[MODEL_A_KEY]["avg_composite"] - summary[MODEL_B_KEY]["avg_composite"]
    summary["composite_margin"] = round(margin, 4)
    summary["winner"] = MODEL_A_NAME if margin >= 0 else MODEL_B_NAME

    EVALUATION_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVALUATION_SUMMARY_PATH.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print_comparison(summary)
    print(f"\nReport written to {write_report(summary)}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-generation", action="store_true", help="Reuse results/generated_*.json")
    parser.add_argument("--limit", type=int, help="Only use the first N scenarios")
    args = parser.parse_args()
    try:
        run_pipeline(skip_generation=args.skip_generation, limit=args.limit)
    except OllamaError as exc:
        raise SystemExit(f"Error: {exc}")


if __name__ == "__main__":
    main()
