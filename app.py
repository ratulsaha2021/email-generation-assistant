"""Local web app for the email generation assistant.

Run:  python app.py            then open http://127.0.0.1:8000
      python app.py --port 9000

Uses only the standard library on top of the pipeline's own modules.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pandas as pd

from constants import (
    BASE_DIR,
    EVALUATION_SUMMARY_PATH,
    GENERATOR_MODEL,
    JUDGE_MODEL,
    MODEL_A_KEY,
    MODEL_B_KEY,
    REFERENCE_KEY,
    RESULTS_PATHS,
    SCENARIOS_PATH,
)
from evaluate import evaluate_single
from generate import PROFILE_NAMES, generate_email, load_scenarios
from llm import OllamaError, ensure_models_available

INDEX_PATH = BASE_DIR / "static" / "index.html"
ORIGINAL_SCENARIOS_PATH = BASE_DIR / "scenarios.original.json"
TONES = ["formal", "casual", "urgent", "empathetic", "assertive"]
MAX_FACTS = 10
SCENARIO_LOCK = threading.Lock()


class PipelineRunner:
    """Runs compare.py in a subprocess and keeps its output for polling."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.process: subprocess.Popen[str] | None = None
        self.log: list[str] = []

    def start(self, limit: int | None) -> bool:
        with self.lock:
            if self.process and self.process.poll() is None:
                return False
            cmd = [sys.executable, "-u", str(BASE_DIR / "compare.py")]
            if limit:
                cmd += ["--limit", str(limit)]
            self.log = [f"$ python compare.py{' --limit ' + str(limit) if limit else ''}"]
            self.process = subprocess.Popen(
                cmd, cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
        threading.Thread(target=self._pump, args=(self.process,), daemon=True).start()
        return True

    def _pump(self, process: subprocess.Popen[str]) -> None:
        assert process.stdout is not None
        for line in process.stdout:
            self.log.append(line.rstrip())

    def status(self) -> dict[str, Any]:
        running = bool(self.process and self.process.poll() is None)
        code = None if running or not self.process else self.process.returncode
        return {"running": running, "returncode": code, "log": self.log[-400:]}


RUNNER = PipelineRunner()


def clean_scenario(body: dict[str, Any]) -> dict[str, Any]:
    """Validate scenario fields from the browser; raises ValueError with a readable message."""
    intent = str(body.get("intent", "")).strip()
    tone = str(body.get("tone", "")).strip().lower()
    raw_facts = body.get("key_facts", [])
    if isinstance(raw_facts, str):
        raw_facts = raw_facts.splitlines()
    facts = [str(f).strip() for f in raw_facts if str(f).strip()]
    reference = str(body.get("human_reference_email") or "").strip()
    if not intent:
        raise ValueError("Write what the email is for.")
    if tone not in TONES:
        raise ValueError(f"Tone must be one of: {', '.join(TONES)}.")
    if not facts:
        raise ValueError("Add at least one key fact, one per line.")
    if len(facts) > MAX_FACTS:
        raise ValueError(f"Use at most {MAX_FACTS} key facts.")
    return {"intent": intent, "key_facts": facts, "tone": tone, "human_reference_email": reference}


def save_scenarios(scenarios: list[dict[str, Any]]) -> None:
    # Keep the shipped test set so it can be restored with "Reset".
    if not ORIGINAL_SCENARIOS_PATH.exists():
        shutil.copyfile(SCENARIOS_PATH, ORIGINAL_SCENARIOS_PATH)
    tmp = SCENARIOS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(scenarios, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, SCENARIOS_PATH)


def change_scenarios(method: str, path: str, body: dict[str, Any]) -> tuple[int, Any]:
    if RUNNER.status()["running"]:
        return 409, {"error": "Wait for the running evaluation to finish before changing scenarios."}
    with SCENARIO_LOCK:
        scenarios = load_scenarios()
        if method == "POST" and path == "/api/scenarios/reset":
            if not ORIGINAL_SCENARIOS_PATH.exists():
                return 200, scenarios
            shutil.copyfile(ORIGINAL_SCENARIOS_PATH, SCENARIOS_PATH)
            return 200, load_scenarios()
        if method == "POST" and path == "/api/scenarios":
            new_id = max((s["scenario_id"] for s in scenarios), default=0) + 1
            scenarios.append({"scenario_id": new_id, **clean_scenario(body)})
            save_scenarios(scenarios)
            return 201, scenarios

        try:
            sid = int(path.rsplit("/", 1)[-1])
        except ValueError:
            return 404, {"error": "Not found"}
        index = next((i for i, s in enumerate(scenarios) if s["scenario_id"] == sid), None)
        if index is None:
            return 404, {"error": f"Scenario {sid} does not exist."}
        if method == "PUT":
            scenarios[index] = {"scenario_id": sid, **clean_scenario(body)}
        elif method == "DELETE":
            if len(scenarios) == 1:
                return 400, {"error": "Keep at least one scenario; the evaluation needs something to test."}
            scenarios.pop(index)
        else:
            return 405, {"error": "Method not allowed"}
        save_scenarios(scenarios)
        return 200, scenarios


def load_results() -> dict[str, Any] | None:
    if not EVALUATION_SUMMARY_PATH.exists():
        return None
    summary = json.loads(EVALUATION_SUMMARY_PATH.read_text(encoding="utf-8"))
    rows = {}
    for key in (MODEL_A_KEY, MODEL_B_KEY, REFERENCE_KEY):
        path = RESULTS_PATHS[key]
        if key in summary and path.exists():
            rows[key] = pd.read_csv(path).fillna("").to_dict(orient="records")
    return {"summary": summary, "rows": rows}


def handle_generate(body: dict[str, Any]) -> dict[str, Any]:
    intent = str(body.get("intent", "")).strip()
    tone = str(body.get("tone", "")).strip().lower()
    facts = [str(f).strip() for f in body.get("key_facts", []) if str(f).strip()]
    profiles = [p for p in body.get("profiles", [MODEL_A_KEY, MODEL_B_KEY]) if p in PROFILE_NAMES]
    if not intent:
        raise ValueError("Write the intent of the email.")
    if not facts:
        raise ValueError("Add at least one key fact, one per line.")
    if tone not in TONES:
        raise ValueError(f"Tone must be one of: {', '.join(TONES)}.")
    if not profiles:
        raise ValueError("Choose at least one prompting strategy.")

    ensure_models_available(GENERATOR_MODEL)
    scenario = {"scenario_id": 0, "intent": intent, "key_facts": facts, "tone": tone}
    emails = {key: generate_email(scenario, key) for key in profiles}

    results = {key: {"name": PROFILE_NAMES[key], "email": email} for key, email in emails.items()}
    if body.get("judge", True):
        ensure_models_available(JUDGE_MODEL)
        for key, email in emails.items():
            results[key]["scores"] = evaluate_single(scenario, email)
    return {"results": results}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}\n")

    def _send(self, status: int, payload: Any, content_type: str = "application/json") -> None:
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX_PATH.read_bytes(), "text/html")
        elif self.path == "/api/config":
            self._send(200, {"generator_model": GENERATOR_MODEL, "judge_model": JUDGE_MODEL, "tones": TONES})
        elif self.path == "/api/scenarios":
            self._send(200, load_scenarios())
        elif self.path == "/api/scenarios/original":
            self._send(200, {"has_backup": ORIGINAL_SCENARIOS_PATH.exists()})
        elif self.path == "/api/results":
            self._send(200, load_results() or {})
        elif self.path == "/api/pipeline":
            self._send(200, RUNNER.status())
        else:
            self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:
        try:
            body = self._body()
            if self.path == "/api/generate":
                self._send(200, handle_generate(body))
            elif self.path.startswith("/api/scenarios"):
                self._send(*change_scenarios("POST", self.path, body))
            elif self.path == "/api/pipeline":
                limit = int(body["limit"]) if body.get("limit") else None
                if not RUNNER.start(limit):
                    self._send(409, {"error": "The evaluation is already running."})
                else:
                    self._send(202, RUNNER.status())
            else:
                self._send(404, {"error": "Not found"})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except OllamaError as exc:
            self._send(503, {"error": str(exc)})

    def do_PUT(self) -> None:
        self._change("PUT")

    def do_DELETE(self) -> None:
        self._change("DELETE")

    def _change(self, method: str) -> None:
        if not self.path.startswith("/api/scenarios/"):
            self._send(404, {"error": "Not found"})
            return
        try:
            body = self._body() if method == "PUT" else {}
            self._send(*change_scenarios(method, self.path, body))
        except ValueError as exc:
            self._send(400, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Email Generation Assistant running at http://{args.host}:{args.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
