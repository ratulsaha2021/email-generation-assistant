"""Shared paths and configuration for the Ollama email generation pipeline.

Model names and the Ollama host can be overridden with environment variables:
    OLLAMA_HOST        default http://localhost:11434
    GENERATOR_MODEL    default gemma4:e4b
    JUDGE_MODEL        default gemma4:26b
"""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "results"
REPORT_DIR = BASE_DIR / "report"
SCENARIOS_PATH = BASE_DIR / "scenarios.json"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = f"http://{OLLAMA_HOST}"

# The judge is deliberately a different (larger) model than the generator so
# the evaluation does not grade its own output.
GENERATOR_MODEL = os.environ.get("GENERATOR_MODEL", "gemma4:e4b")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gemma4:26b")

GENERATION_TEMPERATURE = 0.7
JUDGE_TEMPERATURE = 0.0
SEED = 42

MODEL_A_KEY = "model_a"
MODEL_B_KEY = "model_b"
REFERENCE_KEY = "reference"
MODEL_A_NAME = "few-shot-roleplay"
MODEL_B_NAME = "simple-prompt"
REFERENCE_NAME = "human-reference"

GENERATED_PATHS = {
    MODEL_A_KEY: OUTPUT_DIR / "generated_model_a.json",
    MODEL_B_KEY: OUTPUT_DIR / "generated_model_b.json",
}
RESULTS_PATHS = {
    MODEL_A_KEY: OUTPUT_DIR / "results_model_a.csv",
    MODEL_B_KEY: OUTPUT_DIR / "results_model_b.csv",
    REFERENCE_KEY: OUTPUT_DIR / "results_reference.csv",
}
EVALUATION_SUMMARY_PATH = OUTPUT_DIR / "evaluation_summary.json"
FINAL_REPORT_PATH = REPORT_DIR / "final_report.md"
