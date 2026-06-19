# Email Generation Assistant

## Overview
Email Generation Assistant is a complete evaluation project for comparing two Anthropic models on business email generation. It creates emails from structured scenarios, evaluates them with one rule-based metric and two LLM-as-a-judge metrics, and produces side-by-side model results. The project includes ten realistic business scenarios with human-written reference emails, reusable Python modules, representative result artifacts, and a final evaluation report. It can run with the Anthropic API for live model results or in fully offline mode for no-cost local demos.

## Project Structure
```text
email-generation-assistant/
├── README.md                         # Setup, usage, and project documentation
├── requirements.txt                  # Python dependencies
├── config.py                         # Model names, API key loading, and constants
├── generate.py                       # Prompt templates and email generation logic
├── evaluate.py                       # Fact recall, tone, and fluency evaluation logic
├── compare.py                        # End-to-end orchestration and comparison script
├── scenarios.json                    # Ten business email scenarios and reference emails
├── .env.example                      # Environment variable template
├── .gitignore                        # Keeps secrets and local artifacts out of git
├── results/
│   ├── results_model_a.csv           # Model A scores for all scenarios
│   ├── results_model_b.csv           # Model B scores for all scenarios
│   └── evaluation_summary.json       # Aggregated comparison and winner
└── report/
    └── final_report.md               # Written evaluation report
```

## Setup Instructions
1. Clone the repository.
2. Create and activate a virtual environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies.
   ```bash
   pip install -r requirements.txt
   ```
4. Set the Anthropic API key.
   ```bash
   export ANTHROPIC_API_KEY=your_key_here
   ```
   You can also copy `.env.example` to `.env` and set the value there.
5. Download NLTK data.
   ```bash
   python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('punkt_tab')"
   ```

## How to Run
```bash
# Run the full pipeline (generation + evaluation + comparison)
python compare.py

# Run the full pipeline without an API key
python compare.py --offline

# Run generation only
python generate.py

# Run evaluation only (if generated emails already exist)
python evaluate.py
```

## Outputs
- `results/results_model_a.csv` — Model A scores for all 10 scenarios
- `results/results_model_b.csv` — Model B scores for all 10 scenarios
- `results/evaluation_summary.json` — Side-by-side comparison and winner
- `report/final_report.md` — Full written report

## Offline Mode
Use `python compare.py --offline` when you do not have a paid Anthropic API key. Offline mode uses the local human reference emails as the stronger model profile, deterministic local drafts as the second model profile, the NLTK fact recall metric, and local heuristic replacements for tone and fluency judging. This mode is intended for demos, development, and repository validation; use normal `python compare.py` for live Anthropic model evaluation.

## Prompting Technique
This project uses Chain-of-Thought + Role-Playing. The model reasons through tone analysis, fact mapping, and structure planning inside `<thinking>` tags before generating the final email. This ensures deliberate, consistent, and auditable outputs.

## Metric Descriptions
- Fact Recall Score: Rule-based NLTK keyword overlap check across key facts
- Tone Accuracy Score: LLM-as-a-Judge scoring tone match on a 1-5 scale
- Fluency and Professionalism Score: LLM-as-a-Judge scoring writing quality on a 1-5 scale
