"""Build report/final_report.md directly from the evaluation outputs.

Every number in the report is read from results/, so the report can never
drift from the data. Run standalone to rebuild it: python report.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from constants import (
    EVALUATION_SUMMARY_PATH,
    FINAL_REPORT_PATH,
    MODEL_A_KEY,
    MODEL_B_KEY,
    REFERENCE_KEY,
    RESULTS_PATHS,
)
from evaluate import JUDGE_SYSTEM_PROMPT
from generate import FEW_SHOT_EXAMPLES, FEW_SHOT_SYSTEM_PROMPT, SIMPLE_SYSTEM_PROMPT

METRIC_LABELS = {
    "avg_fact_recall": "Fact Recall",
    "avg_tone_accuracy": "Tone Accuracy",
    "avg_clarity_professionalism": "Clarity & Professionalism",
    "avg_composite": "Composite",
}
# Below this composite margin the two strategies are treated as tied.
NOISE_MARGIN = 0.02


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def _scenario_table(frame: pd.DataFrame) -> str:
    lines = [
        "| # | Intent | Tone | Fact Recall | Tone Acc. | Clarity | Composite | Words | Placeholders |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in frame.itertuples():
        lines.append(
            f"| {row.scenario_id} | {row.intent} | {row.tone} | {row.fact_recall_score:.2f} | "
            f"{row.tone_accuracy_score:.2f} | {row.clarity_professionalism_score:.2f} | "
            f"{row.composite_score:.3f} | {row.word_count} | {row.placeholder_count} |"
        )
    means = frame[["fact_recall_score", "tone_accuracy_score", "clarity_professionalism_score", "composite_score"]].mean()
    lines.append(
        f"| **Avg** | | | **{means.iloc[0]:.3f}** | **{means.iloc[1]:.3f}** | **{means.iloc[2]:.3f}** | "
        f"**{means.iloc[3]:.3f}** | {frame.word_count.mean():.0f} | {frame.placeholder_count.sum()} |"
    )
    return "\n".join(lines)


def _aggregate_table(summary: dict[str, Any]) -> str:
    a, b, ref = summary[MODEL_A_KEY], summary[MODEL_B_KEY], summary.get(REFERENCE_KEY)
    cell = (lambda k, fmt="{}": " " + fmt.format(ref[k]) + " |") if ref else (lambda k, fmt="{}": "")
    lines = [
        f"| Metric | {a['model_name']} | {b['model_name']} | Delta (A - B) |" + (f" {ref['model_name']} |" if ref else ""),
        "|---|---:|---:|---:|" + ("---:|" if ref else ""),
    ]
    for key, label in METRIC_LABELS.items():
        lines.append(f"| {label} | {a[key]:.4f} | {b[key]:.4f} | {a[key] - b[key]:+.4f} |" + cell(key, "{:.4f}"))
    lines.append(f"| Placeholders (total) | {a['total_placeholders']} | {b['total_placeholders']} | |" + cell("total_placeholders"))
    lines.append(f"| Avg word count | {a['avg_word_count']} | {b['avg_word_count']} | |" + cell("avg_word_count"))
    return "\n".join(lines)


def _failure_analysis(frame: pd.DataFrame, name: str) -> str:
    means = {
        "Fact Recall": frame.fact_recall_score.mean(),
        "Tone Accuracy": frame.tone_accuracy_score.mean(),
        "Clarity & Professionalism": frame.clarity_professionalism_score.mean(),
    }
    weakest = min(means, key=means.get)
    parts = [f"The weakest metric for **{name}** was **{weakest}** ({means[weakest]:.3f}).", ""]
    parts.append("Lowest-scoring scenarios:")
    parts.append("")
    for row in frame.nsmallest(3, "composite_score").itertuples():
        detail = f"- **Scenario {row.scenario_id}** ({row.intent}, {row.tone}), composite {row.composite_score:.3f}."
        if isinstance(row.missed_facts, str) and row.missed_facts:
            detail += f" Missed facts: *{row.missed_facts}*."
        if row.placeholder_count:
            detail += f" Contained {row.placeholder_count} unfilled placeholder(s)."
        if isinstance(row.judge_notes, str) and row.judge_notes:
            detail += f" Judge: \"{row.judge_notes.strip()}\""
        parts.append(detail)
    return "\n".join(parts)


def _recommendation(summary: dict[str, Any]) -> str:
    a, b = summary[MODEL_A_KEY], summary[MODEL_B_KEY]
    margin = summary["composite_margin"]
    winner, loser = (a, b) if margin >= 0 else (b, a)
    fact_gap = winner["avg_fact_recall"] - loser["avg_fact_recall"]
    lines = []
    if abs(margin) < NOISE_MARGIN:
        lines.append(
            f"The composite margin ({margin:+.4f}) is below {NOISE_MARGIN}, which is within the noise of a "
            f"{a['scenarios']}-scenario, single-judge evaluation, so the two strategies are **effectively tied** on this data. "
            f"**{winner['model_name']}** is recommended by a narrow margin, but the result should be confirmed "
            f"with more scenarios or repeated runs before relying on it."
        )
    else:
        lines.append(
            f"**{winner['model_name']}** is recommended for production. It leads on composite score by "
            f"{abs(margin):.4f} ({winner['avg_composite']:.4f} vs {loser['avg_composite']:.4f})."
        )
    lines.append("")
    if abs(fact_gap) < 1e-9:
        lines.append(
            f"- Fact recall, the most costly failure in a business email, is identical for both strategies "
            f"({winner['avg_fact_recall']:.4f}), so the difference comes from tone and clarity."
        )
    else:
        lines.append(
            f"- Fact recall, the most costly failure in a business email, differs by {fact_gap:+.4f} "
            f"({winner['model_name']} minus {loser['model_name']})."
        )
    lines.append(
        f"- Unfilled placeholders: {winner['model_name']} produced {winner['total_placeholders']}, "
        f"{loser['model_name']} produced {loser['total_placeholders']}. Any placeholder means the email "
        f"cannot be sent without manual editing."
    )
    ref = summary.get(REFERENCE_KEY)
    if not ref:
        return "\n".join(lines)
    lines.append(
        f"- Calibration: the human reference emails scored {ref['avg_composite']:.4f}. Generated emails scoring "
        f"close to or above this suggests the judge is near its ceiling and cannot separate strong outputs well."
    )
    return "\n".join(lines)


def build_report(summary: dict[str, Any]) -> str:
    frames = {key: pd.read_csv(RESULTS_PATHS[key]) for key in (MODEL_A_KEY, MODEL_B_KEY, REFERENCE_KEY) if key in summary}
    if REFERENCE_KEY in frames:
        calibration = (
            f"Scored on the {len(frames[REFERENCE_KEY])} scenario(s) that include a human reference email.\n\n"
            + _scenario_table(frames[REFERENCE_KEY])
        )
    else:
        calibration = "No scenario includes a human reference email, so there is no baseline for this run."
    a, b = summary[MODEL_A_KEY], summary[MODEL_B_KEY]
    loser_key = MODEL_B_KEY if summary["composite_margin"] >= 0 else MODEL_A_KEY
    example_intents = ", ".join(f"*{e['intent']}* ({e['tone']})" for e in FEW_SHOT_EXAMPLES)
    test_intents = {i.strip().lower() for i in frames[MODEL_A_KEY]["intent"]}
    overlap = [e["intent"] for e in FEW_SHOT_EXAMPLES if e["intent"].strip().lower() in test_intents]
    overlap_note = (
        f"Warning: these demonstration intents also appear in the test scenarios, which favours Model A: {', '.join(overlap)}."
        if overlap
        else "None of the demonstration intents appear in the test scenarios, so the strategy cannot score well by copying an answer."
    )

    return f"""# Email Generation Assistant: Evaluation Report

*This report is generated automatically by `report.py` from the files in `results/`.*

- **Generator model:** `{summary['generator_model']}` (Ollama, temperature 0.7, fixed seed)
- **Judge model:** `{summary['judge_model']}` (Ollama, temperature 0, JSON-schema constrained output)
- **Scenarios:** {a['scenarios']}

The judge is a different, larger model than the generator, so no model grades its own output.

## 1. Prompting Strategies

### Model A: {a['model_name']} (advanced)

Role-playing system prompt plus {len(FEW_SHOT_EXAMPLES)} few-shot demonstrations: {example_intents}.
{overlap_note}

{_quote(FEW_SHOT_SYSTEM_PROMPT)}

### Model B: {b['model_name']} (baseline)

A single instruction with no role and no examples:

{_quote(SIMPLE_SYSTEM_PROMPT)}

Both strategies receive the same user message: the intent, the key facts as a bulleted list, and the tone.

## 2. Metrics (LLM-as-a-Judge)

| Metric | How it is computed |
|---|---|
| Fact Recall | The judge quotes evidence for **each** key fact and marks it present or absent. Score = present / total. |
| Tone Accuracy | 1-5 rubric score for the requested tone, rescaled to 0-1 as (score - 1) / 4. |
| Clarity & Professionalism | 1-5 rubric score (subject, flow, grammar, length, call to action, sign-off, no placeholders), rescaled the same way. |
| Composite | Mean of the three metrics. |

Deterministic diagnostics are recorded alongside: word count, subject-line presence, and the number of unfilled `[placeholders]`.
The human reference emails in `scenarios.json` are scored with the same judge as a calibration baseline.

<details><summary>Judge system prompt</summary>

{_quote(JUDGE_SYSTEM_PROMPT)}

</details>

## 3. Results

### Aggregate

{_aggregate_table(summary)}

**Winner: {summary['winner']}** (composite margin {summary['composite_margin']:+.4f})

### Model A: {a['model_name']}

{_scenario_table(frames[MODEL_A_KEY])}

### Model B: {b['model_name']}

{_scenario_table(frames[MODEL_B_KEY])}

### Calibration: human reference emails

{calibration}

## 4. Comparative Analysis

### Failure modes of the lower-scoring strategy

{_failure_analysis(frames[loser_key], summary[loser_key]['model_name'])}

### Recommendation

{_recommendation(summary)}

### Limitations

- {a['scenarios']} scenario(s) and one judge give a small sample; small score differences are not statistically meaningful.
- LLM judges tend toward lenient scores and can favour longer emails; per-fact evidence and the reference baseline reduce but do not remove this.
- Generation uses a fixed seed, but results can still vary across Ollama versions and hardware.
"""


def write_report(summary: dict[str, Any] | None = None, path: Path = FINAL_REPORT_PATH) -> Path:
    if summary is None:
        with EVALUATION_SUMMARY_PATH.open("r", encoding="utf-8") as f:
            summary = json.load(f)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(summary), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(f"Report written to {write_report()}")
