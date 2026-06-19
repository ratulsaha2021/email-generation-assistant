"""Project configuration for the Email Generation Assistant."""

import os

from dotenv import load_dotenv


load_dotenv(override=True)

MODEL_A = "claude-sonnet-4-6"
MODEL_B = "claude-haiku-4-5-20251001"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MAX_TOKENS = 1024
TEMPERATURE_A = 0.7
TEMPERATURE_B = 0.7
OUTPUT_DIR = "results/"
