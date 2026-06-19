# Email Generation Assistant

## Overview

An AI-powered email generation assistant that uses **Ollama** (local LLM) to produce professional business emails. The project demonstrates **advanced prompt engineering (Few-Shot Prompting with Role-Playing)** and evaluates output quality using **LLM-as-a-Judge** with three custom metrics.

## Project Structure
```text
email-generation-assistant/
├── README.md                         # Setup, usage, and project documentation
├── requirements.txt                  # Python dependencies
├── constants.py                      # Shared paths and profile names
├── generate.py                       # Ollama-based email generation (Few-Shot vs Simple)
├── evaluate.py                       # LLM-as-a-Judge evaluation with 3 custom metrics
├── compare.py                        # End-to-end orchestration script
├── scenarios.json                    # Ten business email scenarios and reference emails
├── .gitignore
├── results/
│   ├── generated_model_a.json        # Raw generated emails (Model A)
│   ├── generated_model_b.json        # Raw generated emails (Model B)
│   ├── results_model_a.csv           # Evaluation scores (Model A)
│   ├── results_model_b.csv           # Evaluation scores (Model B)
│   └── evaluation_summary.json       # Aggregated comparison and winner
└── report/
    └── final_report.md               # Written evaluation report
```

## Prerequisites

- [Ollama](https://ollama.ai) installed and running
- `llama3.2:3b` model pulled (`ollama pull llama3.2:3b`)

## Setup Instructions

1. Clone the repository.
2. Create and activate a virtual environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or: .venv\Scripts\activate  # Windows
   ```
3. Install dependencies.
   ```bash
   pip install -r requirements.txt
   ```
4. Ensure Ollama is running with the model:
   ```bash
   ollama pull llama3.2:3b
   ```

## How to Run

```bash
# Run the full pipeline (generate + evaluate + compare)
python compare.py

# Run generation only
python generate.py

# Run evaluation only (after generated emails exist)
python evaluate.py
```

## Prompting Strategies Compared

### Model A: Few-Shot Prompting with Role-Playing (Advanced)
- **System prompt**: "You are a senior business communications specialist..."
- **Technique**: 2 high-quality example email scenarios are provided before the actual task
- **Expected quality**: Higher — examples guide structure, tone, and fact integration

### Model B: Simple Prompting (Baseline)
- **System prompt**: "Write a professional email based on the given intent, key facts, and tone."
- **Technique**: No examples, no role definition
- **Expected quality**: Lower — less guidance leads to weaker structure and tone

## Custom Metrics (LLM-as-a-Judge)

All three metrics are scored by the same Ollama LLM using a structured evaluation prompt:

1. **Fact Recall Score (0.0–1.0)**: What fraction of required key facts are naturally included in the email? The judge checks semantic presence, not exact keyword matching.

2. **Tone Accuracy Score (0.0–1.0)**: How well does the email match the requested tone (formal, casual, urgent, empathetic, assertive)? The judge evaluates word choice, sentence structure, and overall voice.

3. **Clarity & Professionalism Score (0.0–1.0)**: How clear, well-structured, and professional is the email? The judge evaluates subject line, logical flow, grammar, sentence variety, length appropriateness, and sign-off.

A **Composite Score** is the arithmetic mean of all three.

## Outputs
- `results/results_model_a.csv` — Evaluation scores for Model A (all 10 scenarios)
- `results/results_model_b.csv` — Evaluation scores for Model B (all 10 scenarios)
- `results/evaluation_summary.json` — Side-by-side comparison and winner
- `report/final_report.md` — Full evaluation report
