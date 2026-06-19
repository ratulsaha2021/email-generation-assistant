"""Shared constants for the Ollama-based email generation pipeline."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "results"
SCENARIOS_PATH = BASE_DIR / "scenarios.json"

MODEL_A_KEY = "model_a"
MODEL_B_KEY = "model_b"
MODEL_A_NAME = "few-shot-roleplay"
MODEL_B_NAME = "simple-prompt"

RESULTS_MODEL_A_PATH = OUTPUT_DIR / "results_model_a.csv"
RESULTS_MODEL_B_PATH = OUTPUT_DIR / "results_model_b.csv"
EVALUATION_SUMMARY_PATH = OUTPUT_DIR / "evaluation_summary.json"
