# Email Generation Assistant

## Overview
Email Generation Assistant is a fully offline project for generating and evaluating professional business emails. It uses ten realistic business scenarios, deterministic local generation profiles, and local scoring metrics to compare email quality without external services. The pipeline writes CSV results, a JSON summary, and a markdown report that are ready to share in a public GitHub repository.

## Project Structure
```text
email-generation-assistant/
├── README.md                         # Setup, usage, and project documentation
├── requirements.txt                  # Offline Python dependencies
├── generate.py                       # Deterministic local email generation logic
├── evaluate.py                       # Local fact recall, tone, and fluency metrics
├── compare.py                        # End-to-end offline orchestration script
├── scenarios.json                    # Ten business email scenarios and reference emails
├── .gitignore                        # Keeps local artifacts out of git
├── results/
│   ├── results_model_a.csv           # Offline reference-profile scores
│   ├── results_model_b.csv           # Offline template-profile scores
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
4. Download NLTK data.
   ```bash
   python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('punkt_tab')"
   ```

## How to Run
```bash
# Run the full offline pipeline
python compare.py

# Run generation only
python generate.py

# Run evaluation only after generated emails exist
python evaluate.py
```

## Outputs
- `results/results_model_a.csv` — Offline reference-profile scores for all 10 scenarios
- `results/results_model_b.csv` — Offline template-profile scores for all 10 scenarios
- `results/evaluation_summary.json` — Side-by-side comparison and winner
- `report/final_report.md` — Full written report

## Generation Profiles
- Model A, `offline-reference-profile`: uses the human reference emails from `scenarios.json` as the high-quality generation profile.
- Model B, `offline-template-profile`: creates shorter deterministic drafts from each scenario's intent, tone, and first three key facts.

## Metric Descriptions
- Fact Recall Score: Rule-based NLTK keyword overlap check across key facts.
- Tone Accuracy Score: Local heuristic scoring based on tone-specific language markers.
- Fluency and Professionalism Score: Local heuristic scoring based on subject line, structure, length, sentence count, and sign-off.
